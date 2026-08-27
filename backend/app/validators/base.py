"""Shared validation result helpers for deterministic loan rules."""
from dataclasses import dataclass

@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    rule_name: str
    severity: str
    description: str

RULE_DEFINITIONS = {
    "REQUIRED_FIELDS_PRESENT": RuleDefinition("REQUIRED_FIELDS_PRESENT", "Required Fields Present", "HIGH", "Required loan fields must be populated."),
    "VALID_DATES": RuleDefinition("VALID_DATES", "Valid Dates", "HIGH", "Date values must use valid ISO dates."),
    "VALID_NUMERIC_VALUES": RuleDefinition("VALID_NUMERIC_VALUES", "Valid Numeric Values", "HIGH", "Numeric loan fields must be numeric."),
    "NO_NEGATIVE_PRINCIPAL": RuleDefinition("NO_NEGATIVE_PRINCIPAL", "No Negative Principal", "HIGH", "Original principal cannot be negative."),
    "NO_NEGATIVE_BALANCE": RuleDefinition("NO_NEGATIVE_BALANCE", "No Negative Balance", "HIGH", "Current balance cannot be negative."),
    "MATURITY_AFTER_ORIGINATION": RuleDefinition("MATURITY_AFTER_ORIGINATION", "Maturity After Origination", "HIGH", "Maturity must occur after origination."),
    "BALANCE_NOT_EXCEEDS_PRINCIPAL": RuleDefinition("BALANCE_NOT_EXCEEDS_PRINCIPAL", "Balance Not Greater Than Principal", "HIGH", "Current balance cannot exceed original principal."),
    "INTEREST_RATE_RANGE": RuleDefinition("INTEREST_RATE_RANGE", "Interest Rate Range", "MEDIUM", "Interest rate must be between 0 and 100."),
    "VALID_PAYMENT_STATUS": RuleDefinition("VALID_PAYMENT_STATUS", "Valid Payment Status", "MEDIUM", "Payment status must be recognized."),
    "DUPLICATE_LOAN_ID": RuleDefinition("DUPLICATE_LOAN_ID", "Duplicate Loan ID", "HIGH", "Loan ID must be unique within source evidence."),
    "REQUIRED_DOCUMENT_STATUS": RuleDefinition("REQUIRED_DOCUMENT_STATUS", "Required Document Status", "MEDIUM", "Document status must be COMPLETE."),
    "STALE_RECORD": RuleDefinition("STALE_RECORD", "Stale Record", "MEDIUM", "Loan record must be recently updated."),
    "INVALID_STATE_CODE": RuleDefinition("INVALID_STATE_CODE", "Valid State Code", "MEDIUM", "State must be a valid two-character US code."),
    "PAYMENT_STATUS_CONSISTENCY": RuleDefinition("PAYMENT_STATUS_CONSISTENCY", "Payment Status Consistency", "MEDIUM", "Status and days-past-due must agree."),
    "CLOSED_LOAN_POSITIVE_BALANCE": RuleDefinition("CLOSED_LOAN_POSITIVE_BALANCE", "Closed Loan Positive Balance", "MEDIUM", "Closed loans cannot retain a positive balance."),
    "SUSPICIOUS_DUPLICATE_BORROWER": RuleDefinition("SUSPICIOUS_DUPLICATE_BORROWER", "Suspicious Duplicate Borrower", "MEDIUM", "Repeated borrower/amount/date combinations need review."),
    "CONFLICTING_VALUES": RuleDefinition("CONFLICTING_VALUES", "Conflicting Values", "HIGH", "Conflicting evidence requires human review."),
}
