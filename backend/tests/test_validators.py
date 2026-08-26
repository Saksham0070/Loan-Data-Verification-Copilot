from app.validators import validate_loan
def loan(**changes):
    x={"loan_id":"LN-1","borrower_id":"BR-1","origination_date":"2024-01-01","maturity_date":"2028-01-01","original_principal":1000.0,"current_balance":800.0,"payment_status":"ACTIVE","borrower_state":"CA","document_status":"COMPLETE"};x.update(changes);return x
def test_valid_loan_passes():assert not validate_loan(loan())
def test_balance_over_principal_detected():assert "BALANCE_NOT_EXCEEDS_PRINCIPAL" in {x["rule_id"] for x in validate_loan(loan(current_balance=1100))}
def test_invalid_state_detected():assert "INVALID_STATE_CODE" in {x["rule_id"] for x in validate_loan(loan(borrower_state="XX"))}
