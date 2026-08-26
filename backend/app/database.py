from fastapi import HTTPException, Request
from pymongo import ASCENDING, MongoClient
from .config import get_settings
def create_database():
    s=get_settings()
    # The checked-in/local template intentionally contains angle-bracket
    # placeholders. Treat it exactly like an absent URI so the API can run
    # before Atlas credentials have been provisioned.
    if not s.mongodb_uri or "<" in s.mongodb_uri or ">" in s.mongodb_uri:
        return None
    return MongoClient(s.mongodb_uri,serverSelectionTimeoutMS=5000)[s.mongodb_database]
def ensure_indexes(db):
    db.users.create_index("email",unique=True)
    # A duplicate loan ID is valid source evidence and must be imported so the
    # rule engine can flag it. Only the physical CSV row is unique per upload.
    indexes=db.loans.index_information()
    legacy=indexes.get("loan_id_1_upload_id_1")
    if legacy and legacy.get("unique"):
        db.loans.drop_index("loan_id_1_upload_id_1")
    db.loans.create_index([("loan_id",ASCENDING),("upload_id",ASCENDING),("source_row_number",ASCENDING)],unique=True)
    for c,f in [("loans","borrower_id"),("validation_results","loan_id"),("validation_results","rule_id"),("exceptions","loan_id"),("exceptions","status"),("exceptions","severity"),("ai_reviews","exception_id"),("verified_loans","loan_id"),("audit_logs","loan_id"),("audit_logs","timestamp")]:getattr(db,c).create_index(f)
def get_db(request:Request):
    if request.app.state.db is None:raise HTTPException(503,"Database is not configured. Set MONGODB_URI on the backend.")
    return request.app.state.db
