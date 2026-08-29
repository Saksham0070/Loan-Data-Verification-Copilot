import json
import sys
import types
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.routers import workflow


class InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class InsertManyResult:
    def __init__(self, inserted_ids):
        self.inserted_ids = inserted_ids


class Collection:
    def __init__(self, documents=None):
        self.documents = documents or []

    def find_one(self, query):
        for document in self.documents:
            if self._matches(document, query):
                return document
        return None

    @staticmethod
    def _matches(document, query):
        for key, value in query.items():
            actual = document.get(key)
            if isinstance(value, dict) and "$ne" in value:
                if actual == value["$ne"]:
                    return False
            elif isinstance(value, dict) and "$in" in value:
                if actual not in value["$in"]:
                    return False
            elif actual != value:
                return False
        return True

    def find(self, query=None, *_):
        return [document for document in self.documents if self._matches(document, query or {})]

    def count_documents(self, query):
        return len(self.find(query))

    def insert_one(self, document):
        document.setdefault("_id", ObjectId())
        self.documents.append(document)
        return InsertResult(document["_id"])

    def insert_many(self, documents):
        return InsertManyResult([self.insert_one(document).inserted_id for document in documents])

    def update_one(self, query, update):
        document = self.find_one(query)
        if document:
            document.update(update.get("$set", {}))


class Database:
    def __init__(self, exception, loan):
        self.exceptions = Collection([exception])
        self.loans = Collection([loan])
        self.ai_reviews = Collection()
        self.review_decisions = Collection()
        self.validation_results = Collection()
        self.verified_loans = Collection()
        self.audit_logs = Collection()
        self.source_records = Collection()


def make_database():
    loan_id = ObjectId()
    exception_id = ObjectId()
    loan = {"_id": loan_id, "loan_id": "LN-AI-1", "borrower_id":"BR-AI-1","origination_date":"2024-01-01","maturity_date":"2028-01-01","original_principal":1000.0,"current_balance":800.0,"payment_status":"ACTIVE","borrower_state":"CA","document_status":"COMPLETE","upload_id":ObjectId()}
    exception = {
        "_id": exception_id,
        "loan_id": "LN-AI-1",
        "loan_document_id": loan_id,
        "description": "Current balance conflicts with servicing source.",
        "affected_fields": ["current_balance"],
    }
    return Database(exception, loan), exception, loan


def test_ai_recommendation_is_logged_but_never_changes_loan(monkeypatch):
    db, exception, loan = make_database()
    response = {
        "severity": "HIGH",
        "explanation": "The servicing source reports a different balance.",
        "suggested_field": "current_balance",
        "suggested_value": 750.0,
        "confidence": 0.88,
        "reasoning": "Use the more recent servicing source after review.",
    }

    class FakeGroq:
        def __init__(self, **_):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **__: SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(response)))]
                    )
                )
            )

    fake_module = types.ModuleType("groq")
    fake_module.Groq = FakeGroq
    monkeypatch.setitem(sys.modules, "groq", fake_module)
    monkeypatch.setattr(
        workflow,
        "get_settings",
        lambda: SimpleNamespace(groq_api_key="test-key", groq_model="test-model"),
    )

    review = workflow.ai_review(str(exception["_id"]), {"_id": ObjectId()}, db)

    assert db.loans.documents[0]["current_balance"] == 800.0
    assert review["model"] == "test-model"
    assert review["prompt"]
    assert review["created_at"]
    generated = db.audit_logs.documents[-1]
    assert generated["event_type"] == "AI_RECOMMENDATION_GENERATED"
    assert generated["metadata"]["suggested_value"] == 750.0


def test_ai_review_parser_strips_qwen_thinking_and_keeps_json_recommendation():
    _, exception, _ = make_database()
    response = workflow._parse_ai_review_response(
        '<think>private reasoning</think>{"severity":"MEDIUM","explanation":"The balance needs review.","suggested_field":"current_balance","suggested_value":0,"confidence":"HIGH","reasoning":"A closed loan should not retain a balance."}',
        exception,
    )

    assert response["suggested_field"] == "current_balance"
    assert response["suggested_value"] == 0
    assert "think" not in str(response).lower()


def test_conflict_ai_review_stores_side_by_side_source_evidence(monkeypatch):
    db, exception, _ = make_database()
    exception["rule_id"] = "CONFLICTING_VALUES"
    db.source_records.insert_one({"loan_id": "LN-AI-1", "source_type": "SERVICER_UPDATE", "source_row_number": 2, "raw_row": {"current_balance": 750.0, "last_updated_at": "2026-08-01"}})
    response = {"severity": "HIGH", "explanation": "The servicing update is newer.", "suggested_field": "current_balance", "suggested_value": 750.0, "confidence": "HIGH", "recommended_source": "SERVICER_UPDATE", "comparison_reasoning": "It has the newer update timestamp."}

    class FakeGroq:
        def __init__(self, **_):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **__: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(response)))])))

    module = types.ModuleType("groq")
    module.Groq = FakeGroq
    monkeypatch.setitem(sys.modules, "groq", module)
    monkeypatch.setattr(workflow, "get_settings", lambda: SimpleNamespace(groq_api_key="test-key", groq_model="test-model"))

    review = workflow.ai_review(str(exception["_id"]), {"_id": ObjectId()}, db)

    assert len(review["source_comparison"]) == 2
    assert review["source_comparison"][1]["values"]["current_balance"] == 750.0
    assert review["response"]["recommended_source"] == "SERVICER_UPDATE"
    assert "SERVICER_UPDATE" in review["prompt"]


def test_only_explicit_human_acceptance_applies_the_stored_ai_suggestion():
    db, exception, loan = make_database()
    loan["borrower_state"] = "TX"
    ai_review_id = ObjectId()
    db.ai_reviews.insert_one(
        {
            "_id": ai_review_id,
            "exception_id": exception["_id"],
            "response": {"suggested_field": "current_balance", "suggested_value": 750.0},
        }
    )

    decision = workflow.decide(
        str(exception["_id"]),
        workflow.Decision(
            decision="ACCEPT",
            ai_review_id=str(ai_review_id),
            field="borrower_state",
            final_value="CA",
            comment="I checked the source evidence and accept this suggestion.",
        ),
        {"_id": ObjectId()},
        db,
    )

    assert db.loans.documents[0]["current_balance"] == 750.0
    assert db.loans.documents[0]["borrower_state"] == "TX"
    assert decision["ai_review_id"] == str(ai_review_id)
    assert decision["post_edit_validation"]["aggregate_status"] == "READY_FOR_VERIFICATION"
    assert any(event["event_type"] == "AI_RECOMMENDATION_ACCEPTED" for event in db.audit_logs.documents)
    assert db.audit_logs.documents[-1]["event_type"] == "POST_EDIT_VALIDATION_EXECUTED"


def test_acceptance_without_stored_ai_or_unsafe_edit_is_rejected():
    db, exception, _ = make_database()
    user = {"_id": ObjectId()}

    with pytest.raises(HTTPException, match="requires ai_review_id"):
        workflow.decide(
            str(exception["_id"]),
            workflow.Decision(decision="ACCEPT", comment="No stored AI recommendation."),
            user,
            db,
        )


def test_request_correction_preserves_loan_and_blocks_verification():
    db, exception, loan = make_database()
    user = {"_id": ObjectId()}

    decision = workflow.decide(
        str(exception["_id"]),
        workflow.Decision(decision="REQUEST_CORRECTION", comment="Please correct the servicing file."),
        user,
        db,
    )

    assert decision["decision"] == "REQUEST_CORRECTION"
    assert db.exceptions.documents[0]["status"] == "CORRECTION_REQUESTED"
    assert loan["current_balance"] == 800.0
    assert any(event["event_type"] == "CORRECTION_REQUESTED" for event in db.audit_logs.documents)
    with pytest.raises(HTTPException, match="Resolve every open exception"):
        workflow.verify(str(exception["_id"]), user, db)


def test_verified_record_requires_clean_final_validation_and_is_created_once():
    db, exception, _ = make_database()
    exception["status"] = "CORRECTED"
    user = {"_id": ObjectId()}

    verified = workflow.verify(str(exception["_id"]), user, db)

    assert verified["quality_score"] == 100
    assert len(db.verified_loans.documents) == 1
    assert db.loans.documents[0]["aggregate_status"] == "VERIFIED"
    assert db.audit_logs.documents[-1]["event_type"] == "VERIFIED_RECORD_CREATED"
    with pytest.raises(HTTPException, match="already has a verified record"):
        workflow.verify(str(exception["_id"]), user, db)

    exception["status"] = "OPEN"
    with pytest.raises(HTTPException, match="allowed field"):
        workflow.decide(
            str(exception["_id"]),
            workflow.Decision(
                decision="EDIT",
                field="raw_csv_row",
                final_value={"tampered": True},
                comment="This must not be editable.",
            ),
            user,
            db,
        )


def test_resolved_exception_cannot_request_ai_or_receive_another_decision():
    db, exception, _ = make_database()
    exception["status"] = "AUTO_RESOLVED"
    user = {"_id": ObjectId()}

    with pytest.raises(HTTPException, match="active exception"):
        workflow.ai_review(str(exception["_id"]), user, db)
    with pytest.raises(HTTPException, match="resolved exception"):
        workflow.decide(
            str(exception["_id"]),
            workflow.Decision(decision="REJECT", comment="This is already resolved."),
            user,
            db,
        )


def test_clean_loan_can_be_verified_without_an_exception():
    db, _, loan = make_database()
    user = {"_id": ObjectId()}

    verified = workflow.verify_clean_loan("LN-AI-1", user, db)

    assert verified["loan_id"] == "LN-AI-1"
    assert verified["status"] == "VERIFIED"
    assert db.loans.documents[0]["aggregate_status"] == "VERIFIED"
