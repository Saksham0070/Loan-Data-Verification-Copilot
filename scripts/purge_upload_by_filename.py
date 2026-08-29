"""Safely remove one uploaded batch and the workflow records linked to it.

Example:
    python scripts/purge_upload_by_filename.py --filename sample_loans.csv --confirm
"""

import argparse
import os
import sys
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings


def count_targets(database, upload_ids, loan_document_ids, loan_ids, exception_ids):
    upload_strings = [str(upload_id) for upload_id in upload_ids]
    return {
        "uploads": database.uploads.count_documents({"_id": {"$in": upload_ids}}),
        "loans": database.loans.count_documents({"_id": {"$in": loan_document_ids}}),
        "validation_results": database.validation_results.count_documents(
            {"$or": [{"upload_id": {"$in": upload_ids}}, {"loan_document_id": {"$in": loan_document_ids}}]}
        ),
        "exceptions": database.exceptions.count_documents({"loan_document_id": {"$in": loan_document_ids}}),
        "exception_comments": database.exception_comments.count_documents({"exception_id": {"$in": exception_ids}}),
        "ai_reviews": database.ai_reviews.count_documents(
            {"$or": [{"exception_id": {"$in": exception_ids}}, {"loan_id": {"$in": loan_ids}}]}
        ),
        "review_decisions": database.review_decisions.count_documents({"exception_id": {"$in": exception_ids}}),
        "verified_loans": database.verified_loans.count_documents({"loan_document_id": {"$in": loan_document_ids}}),
        "source_records": database.source_records.count_documents({"upload_id": {"$in": upload_ids}}),
        "audit_logs": database.audit_logs.count_documents(
            {"$or": [{"loan_id": {"$in": loan_ids}}, {"metadata.upload_id": {"$in": upload_strings}}]}
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename", required=True, help="Exact uploaded CSV filename to remove")
    parser.add_argument("--confirm", action="store_true", help="Perform deletion after showing target counts")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.mongodb_uri or "<" in settings.mongodb_uri or ">" in settings.mongodb_uri:
        raise SystemExit("MongoDB is not configured. Set MONGODB_URI in backend/.env first.")

    database = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)[settings.mongodb_database]
    uploads = list(database.uploads.find({"filename": args.filename}, {"_id": 1}))
    upload_ids = [item["_id"] for item in uploads]
    if not upload_ids:
        print(f"No uploads found with filename: {args.filename}")
        return

    loans = list(database.loans.find({"upload_id": {"$in": upload_ids}}, {"_id": 1, "loan_id": 1}))
    loan_document_ids = [item["_id"] for item in loans]
    loan_ids = sorted({item.get("loan_id") for item in loans if item.get("loan_id")})
    exceptions = list(database.exceptions.find({"loan_document_id": {"$in": loan_document_ids}}, {"_id": 1}))
    exception_ids = [item["_id"] for item in exceptions]
    counts = count_targets(database, upload_ids, loan_document_ids, loan_ids, exception_ids)

    print(f"Target batch: {args.filename}")
    for collection_name, count in counts.items():
        print(f"{collection_name}: {count}")
    if not args.confirm:
        print("Dry run only. Re-run with --confirm to delete these exact linked records.")
        return

    database.exception_comments.delete_many({"exception_id": {"$in": exception_ids}})
    database.ai_reviews.delete_many({"$or": [{"exception_id": {"$in": exception_ids}}, {"loan_id": {"$in": loan_ids}}]})
    database.review_decisions.delete_many({"exception_id": {"$in": exception_ids}})
    database.verified_loans.delete_many({"loan_document_id": {"$in": loan_document_ids}})
    database.validation_results.delete_many({"$or": [{"upload_id": {"$in": upload_ids}}, {"loan_document_id": {"$in": loan_document_ids}}]})
    database.exceptions.delete_many({"loan_document_id": {"$in": loan_document_ids}})
    database.source_records.delete_many({"upload_id": {"$in": upload_ids}})
    database.audit_logs.delete_many(
        {"$or": [{"loan_id": {"$in": loan_ids}}, {"metadata.upload_id": {"$in": [str(upload_id) for upload_id in upload_ids]}}]}
    )
    database.loans.delete_many({"_id": {"$in": loan_document_ids}})
    database.uploads.delete_many({"_id": {"$in": upload_ids}})
    print("Targeted cleanup complete. User accounts and CSV files were preserved.")


if __name__ == "__main__":
    main()
