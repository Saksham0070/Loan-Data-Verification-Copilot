"""Clear local hackathon workflow data while preserving user accounts.

Run from the repository root: python scripts/reset_demo_data.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from pymongo import MongoClient


DEMO_COLLECTIONS = (
    "uploads",
    "loans",
    "failed_rows",
    "validation_results",
    "exceptions",
    "exception_comments",
    "ai_reviews",
    "review_decisions",
    "verified_loans",
    "audit_logs",
)


def main():
    settings = get_settings()
    if not settings.mongodb_uri or "<" in settings.mongodb_uri or ">" in settings.mongodb_uri:
        raise SystemExit("MongoDB is not configured. Set MONGODB_URI in backend/.env first.")
    database = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)[settings.mongodb_database]
    deleted = {}
    for collection_name in DEMO_COLLECTIONS:
        deleted[collection_name] = database[collection_name].delete_many({}).deleted_count
    print("Demo workflow data reset complete. User accounts were preserved.")
    for collection_name, count in deleted.items():
        print(f"{collection_name}: {count} deleted")


if __name__ == "__main__":
    main()
