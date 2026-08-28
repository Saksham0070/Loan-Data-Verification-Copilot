"""Backfill aggregate statuses after validation-rule changes.

This preserves loans and audit history. It only runs the deterministic validation
engine again and synchronizes current exception/status information.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))

from app.database import create_database, ensure_indexes
from app.services import revalidate_loan


def main():
    db = create_database()
    if db is None:
        raise SystemExit("MongoDB is not configured.")
    ensure_indexes(db)
    system_user = {"_id": None}
    total = 0
    statuses = {}
    for loan in db.loans.find():
        result = revalidate_loan(db, loan, system_user, "Status backfill after workflow upgrade")
        total += 1
        statuses[result["aggregate_status"]] = statuses.get(result["aggregate_status"], 0) + 1
    print(f"Revalidated {total} loans.")
    print(statuses)


if __name__ == "__main__":
    main()
