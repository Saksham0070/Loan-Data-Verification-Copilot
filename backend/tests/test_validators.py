from app.validators import validate_loan
from app.schemas import NormalizedLoanRecord,normalized_schema_errors
from app.services import aggregate_status,canonical_hash,combined_validation_failures,normalize_with_lineage,quality_from_failures
from app.routers.advanced import _structured_batch_summary,_structured_rule_proposal
def loan(**changes):
    x={"loan_id":"LN-1","borrower_id":"BR-1","origination_date":"2024-01-01","maturity_date":"2028-01-01","original_principal":1000.0,"current_balance":800.0,"payment_status":"ACTIVE","borrower_state":"CA","document_status":"COMPLETE"};x.update(changes);return x
def test_valid_loan_passes():assert not validate_loan(loan())
def test_balance_over_principal_detected():assert "BALANCE_NOT_EXCEEDS_PRINCIPAL" in {x["rule_id"] for x in validate_loan(loan(current_balance=1100))}
def test_invalid_state_detected():assert "INVALID_STATE_CODE" in {x["rule_id"] for x in validate_loan(loan(borrower_state="XX"))}
def test_closed_loan_positive_balance_detected():assert "CLOSED_LOAN_POSITIVE_BALANCE" in {x["rule_id"] for x in validate_loan(loan(payment_status="CLOSED"))}
def test_interest_rate_range_detected():assert "INTEREST_RATE_RANGE" in {x["rule_id"] for x in validate_loan(loan(interest_rate=101))}
def test_duplicate_borrower_combination_detected():assert "SUSPICIOUS_DUPLICATE_BORROWER" in {x["rule_id"] for x in validate_loan(loan(),duplicate_borrower_record=True)}
def test_inconsistent_delinquency_detected():assert "PAYMENT_STATUS_CONSISTENCY" in {x["rule_id"] for x in validate_loan(loan(payment_status="DELINQUENT",days_past_due=0))}
def test_current_or_closed_loan_with_days_past_due_is_detected():
    assert "PAYMENT_STATUS_CONSISTENCY" in {x["rule_id"] for x in validate_loan(loan(payment_status="CURRENT",days_past_due=3))}
    assert "PAYMENT_STATUS_CONSISTENCY" in {x["rule_id"] for x in validate_loan(loan(payment_status="CLOSED",days_past_due=1))}
def test_normalization_creates_canonical_values_and_preserves_lineage():
    raw={" Loan ID ":" ln-101 ","Borrower State":" ca ","Original Principal":"$100,000","Current Balance":"82,500","Interest Rate":"8.5%","Origination Date":"01/15/2024","Maturity Date":"2029-01-15","Payment Status":" active "}
    normalized,changes=normalize_with_lineage(raw)
    assert normalized["loan_id"]=="LN-101"
    assert normalized["borrower_state"]=="CA"
    assert normalized["original_principal"]==100000.0
    assert normalized["current_balance"]==82500.0
    assert normalized["interest_rate"]==8.5
    assert normalized["origination_date"]=="2024-01-15"
    assert raw[" Loan ID "]==" ln-101 "
    assert any(item["canonical_field"]=="loan_id" for item in changes)
def test_invalid_date_is_preserved_for_validation_not_silently_corrected():
    normalized,_=normalize_with_lineage({"Origination Date":"not-a-date"})
    assert normalized["origination_date"]=="not-a-date"
def test_canonical_record_hash_is_stable_for_equivalent_data():
    assert canonical_hash({"loan_id":"LN-1","balance":800})==canonical_hash({"balance":800,"loan_id":"LN-1"})
def test_all_organizer_example_fields_are_retained_in_canonical_schema():
    raw={"loan_id":"ln-200","borrower_id":"br-200","loan_type":"personal","origination_date":"2024-01-01","maturity_date":"2028-01-01","original_principal":"10000","current_balance":"9000","interest_rate":"7.5","term_months":"48","borrower_state":"ca","loan_purpose":"debt consolidation","credit_grade":"b","employment_length":"5","income_band":"50k-75k","payment_status":"active","days_past_due":"0","servicer_name":"Demo Servicer","last_payment_date":"2025-01-01","last_updated_at":"2025-01-02","document_status":"complete","source_system":"origination api"}
    normalized,_=normalize_with_lineage(raw)
    expected=set(raw)
    assert expected <= set(normalized)
    assert normalized["source_system"]=="ORIGINATION API"
    assert normalized["loan_purpose"]=="debt consolidation"
    assert normalized["term_months"]==48
def test_quality_only_penalizes_failed_rules_not_passed_rules():
    assert quality_from_failures([{"severity":"HIGH","passed":True},{"severity":"MEDIUM","passed":True}])==100
    assert quality_from_failures([{"severity":"HIGH","passed":False},{"severity":"MEDIUM","passed":False}])==78
def test_aggregate_status_reflects_blocking_and_review_findings():
    assert aggregate_status([])=="READY_FOR_VERIFICATION"
    assert aggregate_status([{"severity":"MEDIUM"}])=="NEEDS_REVIEW"
    assert aggregate_status([{"severity":"HIGH"}])=="FAILED"
def test_typed_normalized_schema_accepts_clean_canonical_record_and_reports_invalid_type():
    NormalizedLoanRecord.model_validate(loan())
    errors=normalized_schema_errors(loan(original_principal="not-a-number"))
    assert errors[0]["field"]=="original_principal"
    assert "NORMALIZED_SCHEMA_VALID" in {item["rule_id"] for item in combined_validation_failures(loan(original_principal="not-a-number"))}
def test_batch_ai_summary_strips_thinking_and_returns_reviewer_structure():
    exceptions=[{"loan_id":"LN-1","title":"Balance is too high","severity":"HIGH"}]
    raw="<think>private model reasoning</think>{\"overall_assessment\":\"One balance issue needs attention.\",\"risk_level\":\"HIGH\",\"priority_actions\":[{\"priority\":1,\"action\":\"Review LN-1\",\"why\":\"The balance needs confirmation.\",\"affected_loan_ids\":[\"LN-1\"]}],\"issue_groups\":[{\"issue_type\":\"Balance check\",\"severity\":\"HIGH\",\"affected_loan_ids\":[\"LN-1\"],\"what_it_means\":\"The balance may be inaccurate.\",\"recommended_reviewer_action\":\"Compare the source values.\"}],\"reviewer_note\":\"Confirm the evidence first.\"}"
    result=_structured_batch_summary(raw,exceptions)
    assert result["overall_assessment"]=="One balance issue needs attention."
    assert result["issue_groups"][0]["affected_loan_ids"]==["LN-1"]
    assert "think" not in str(result).lower()
def test_rule_ai_response_strips_thinking_and_handles_questions_without_a_rule():
    raw="<think>private model reasoning</think>{\"plain_language_interpretation\":\"This is a question about an existing review instruction.\",\"is_rule_recommended\":false,\"recommended_next_step\":\"Open the exception and review its evidence.\",\"proposed_rule\":null,\"test_cases\":[],\"reviewer_note\":\"No system change is needed.\"}"
    result=_structured_rule_proposal(raw,"Why does this loan need reviewer action?")
    assert result["is_rule_recommended"] is False
    assert result["proposed_rule"] is None
    assert result["plain_language_interpretation"].startswith("This is a question")
    assert "think" not in str(result).lower()
def test_rule_fallback_recognizes_an_existing_closed_loan_balance_rule():
    result=_structured_rule_proposal("<think>unstructured response</think>","Flag loans marked closed when their current balance is greater than zero.")
    assert result["is_rule_recommended"] is False
    assert result["existing_rule"]["rule_id"]=="CLOSED_LOAN_POSITIVE_BALANCE"
    assert "already covered" in result["plain_language_interpretation"].lower()
def test_rule_fallback_creates_a_useful_draft_for_an_unknown_flag_condition():
    result=_structured_rule_proposal("not json","Flag loans with an unusual servicing reference format.")
    assert result["is_rule_recommended"] is True
    assert result["proposed_rule"]["rule_id"]=="PROPOSED_CUSTOM_RULE"
