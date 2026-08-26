from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from ..database import get_db
from ..security import create_token,hash_password,verify_password
from ..services import audit
from ..utils import serialize
router=APIRouter(prefix="/auth",tags=["Authentication"])
class Credentials(BaseModel):email:str=Field(min_length=3);password:str=Field(min_length=8)
class Registration(Credentials):name:str=Field(min_length=2);role:str="DATA_OPERATOR"
@router.post("/register",status_code=201)
def register(p:Registration,db=Depends(get_db)):
    if p.role not in {"DATA_OPERATOR","REVIEWER","DATA_CONSUMER","ADMIN"}:raise HTTPException(422,"Invalid role")
    if db.users.find_one({"email":p.email.lower()}):raise HTTPException(409,"Email already registered")
    u={"email":p.email.lower(),"name":p.name,"role":p.role,"password_hash":hash_password(p.password),"is_active":True,"created_at":datetime.now(timezone.utc)};u["_id"]=db.users.insert_one(u).inserted_id;audit(db,"USER_REGISTERED",u,None,"User registered.");return {"access_token":create_token(u),"token_type":"bearer","user":serialize({k:v for k,v in u.items() if k!="password_hash"})}
@router.post("/login")
def login(p:Credentials,db=Depends(get_db)):
    u=db.users.find_one({"email":p.email.lower(),"is_active":True})
    if not u or not verify_password(p.password,u["password_hash"]):raise HTTPException(401,"Invalid email or password")
    audit(db,"LOGIN",u,None,"User logged in.");return {"access_token":create_token(u),"token_type":"bearer","user":serialize({k:v for k,v in u.items() if k!="password_hash"})}
