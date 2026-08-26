from datetime import datetime,timedelta,timezone
import bcrypt,jwt
from bson import ObjectId
from fastapi import Depends,HTTPException
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from .config import get_settings
from .database import get_db
bearer=HTTPBearer(auto_error=False)
def hash_password(password):return bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()
def verify_password(password,hashed):return bcrypt.checkpw(password.encode(),hashed.encode())
def create_token(user):
    s=get_settings();now=datetime.now(timezone.utc);return jwt.encode({"sub":str(user["_id"]),"role":user["role"],"email":user["email"],"exp":now+timedelta(minutes=s.jwt_expiry_minutes)},s.jwt_secret,algorithm="HS256")
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db=Depends(get_db)):
    if not credentials:raise HTTPException(401,"Authentication required")
    try:payload=jwt.decode(credentials.credentials,get_settings().jwt_secret,algorithms=["HS256"])
    except jwt.PyJWTError as exc:raise HTTPException(401,"Invalid or expired token") from exc
    user=db.users.find_one({"_id":ObjectId(payload["sub"]),"is_active":True})
    if not user:raise HTTPException(401,"User is not active")
    return user
def require_roles(*roles):
    def check(user=Depends(current_user)):
        if user["role"] not in roles:raise HTTPException(403,"This role cannot perform that action")
        return user
    return check
