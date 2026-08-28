from app.validators import validate_loan
from app.schemas import NormalizedLoanRecord,normalized_schema_errors
from app.services import aggregate_status,canonical_hash,combined_validation_failures,normalize_with_lineage,quality_from_failures
def loan(**changes):
    x={"loan_id":"LN-1","borrower_id":"BR-1","origination_date":"2024-01-01","maturity_date":"2028-01-01","original_principal":1000.0,"current_balance":800.0,"payment_status":"ACTIVE","borrower_state":"CA","document_status":"COMPLETE"};x.update(changes);return x
def test_valid_loan_passes():assert not validate_loan(loan())
def test_balance_over_principal_detected():assert "BALANCE_NOT_EXCEEDS_PRINCIPAL" in {x["rule_id"] for x in validate_loan(loan(current_balance=1100))}
def test_invalid_state_detected():assert "INVALID_STATE_CODE" in {x["rule_id"] for x in validate_loan(loan(borrower_state="XX"))}
def test_closed_loan_positive_balance_detected():assert "CLOSED_LOAN_POSITIVE_BALANCE" in {x["rule_id"] for x in validate_loan(loan(payment_status="CLOSED"))}
def test_interest_rate_range_detected():assert "INTEREST_RATE_RANGE" in {x["rule_id"] for x in validate_loan(loan(interest_rate=101))}
def test_duplicate_borrower_combination_detected():assert "SUSPICIOUS_DUPLICATE_BORROWER" in {x["rule_id"] for x in validate_loan(loan(),duplicate_borrower_record=True)}
def test_inconsistent_delinquency_detected():assert "PAYMENT_STATUS_CONSISTENCY" in {x["rule_id"] for x in validate_loan(loan(payment_status="DELINQUENT",days_past_due=0))}
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
