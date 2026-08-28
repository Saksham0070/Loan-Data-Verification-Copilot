"""Canonical, normalized loan-record contract.

The ingestion normalizer is intentionally responsible for cleaning source
formatting.  This model is a second guardrail: it confirms that the resulting
canonical record has the expected types before validation/review continues.
It never changes source data or silently coerces an invalid value.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


class NormalizedLoanRecord(BaseModel):
    """Internal schema for the organizer's loan-tape field set."""

    model_config = ConfigDict(extra="allow", strict=True)

    loan_id: str | None = None
    borrower_id: str | None = None
    loan_type: str | None = None
    origination_date: str | None = None
    maturity_date: str | None = None
    original_principal: float | None = None
    current_balance: float | None = None
    interest_rate: float | None = None
    term_months: int | None = None
    borrower_state: str | None = None
    loan_purpose: str | None = None
    credit_grade: str | None = None
    employment_length: int | float | str | None = None
    income_band: str | None = None
    payment_status: str | None = None
    days_past_due: int | None = None
    servicer_name: str | None = None
    last_payment_date: str | None = None
    last_updated_at: str | None = None
    document_status: str | None = None
    source_system: str | None = None


def normalized_schema_errors(record: dict[str, Any]) -> list[dict[str, str]]:
    """Return serializable schema issues without mutating the canonical row."""

    try:
        NormalizedLoanRecord.model_validate(record)
    except ValidationError as error:
        return [
            {
                "field": ".".join(str(part) for part in issue["loc"]),
                "message": issue["msg"],
            }
            for issue in error.errors()
        ]
    return []
