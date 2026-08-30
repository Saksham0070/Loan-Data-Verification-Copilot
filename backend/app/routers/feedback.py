from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from ..database import get_db
from ..security import current_user
from ..utils import serialize


router = APIRouter(prefix="/feedback", tags=["Feedback"])


class FeedbackSubmission(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    feedback: str = Field(min_length=5, max_length=1000)

    @field_validator("name", "feedback")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field cannot be blank.")
        return value


@router.post("", status_code=201)
def submit_feedback(
    payload: FeedbackSubmission,
    user=Depends(current_user),
    db=Depends(get_db),
):
    """Store optional authenticated product feedback without affecting loan data."""
    document = {
        "name": payload.name.strip(),
        "feedback": payload.feedback.strip(),
        "submitted_by": user["_id"],
        "submitted_by_role": user["role"],
        "submitted_at": datetime.now(timezone.utc),
    }
    document["_id"] = db.feedback.insert_one(document).inserted_id
    return serialize(
        {"_id": document["_id"], "message": "Thank you for helping us improve."}
    )
