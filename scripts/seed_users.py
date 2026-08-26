"""Create safe demo accounts. Run from backend: python ../scripts/seed_users.py"""
from datetime import datetime, timezone
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database import create_database, ensure_indexes
from app.security import hash_password
db=create_database()
if db is None: raise SystemExit("Set MONGODB_URI in backend/.env before seeding users.")
ensure_indexes(db)
for email,name,role in [("operator@demo.local","Demo Operator","DATA_OPERATOR"),("reviewer@demo.local","Demo Reviewer","REVIEWER"),("consumer@demo.local","Demo Consumer","DATA_CONSUMER")]:
    db.users.update_one({"email":email},{"$setOnInsert":{"email":email,"name":name,"role":role,"password_hash":hash_password("DemoPass123!"),"is_active":True,"created_at":datetime.now(timezone.utc)}},upsert=True)
print("Demo users ready. Password for all accounts: DemoPass123!")
