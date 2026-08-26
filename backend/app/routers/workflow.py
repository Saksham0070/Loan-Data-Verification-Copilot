from datetime import datetime,timezone
import json
from bson import ObjectId
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import StreamingResponse
from io import StringIO
import csv
from pydantic import BaseModel,Field
from ..config import get_settings
from ..database import get_db
from ..security import require_roles
from ..services import audit,canonical_hash
from ..utils import serialize
router=APIRouter(tags=["Review workflow"])
class Decision(BaseModel):decision:str;field:str|None=None;final_value:object|None=None;comment:str=Field(min_length=1)
class Comment(BaseModel):body:str=Field(min_length=1,max_length=2000)
@router.get("/exceptions")
def queue(status:str|None=None,severity:str|None=None,search:str|None=None,user=Depends(require_roles("DATA_OPERATOR","REVIEWER","ADMIN")),db=Depends(get_db)):
    q={k:v for k,v in {"status":status,"severity":severity}.items() if v}
    if search:q["loan_id"]={"$regex":search,"$options":"i"}
    return [serialize(x) for x in db.exceptions.find(q).sort("created_at",-1).limit(200)]
@router.post("/exceptions/{exception_id}/claim")
def claim(exception_id:str,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    item=db.exceptions.find_one_and_update({"_id":ObjectId(exception_id),"status":"OPEN"},{"$set":{"status":"UNDER_REVIEW","assigned_to":user["_id"],"updated_at":datetime.now(timezone.utc)}},return_document=True)
    if not item:raise HTTPException(409,"Exception is no longer available to claim")
    audit(db,"EXCEPTION_UNDER_REVIEW",user,item["loan_id"],"Reviewer claimed exception.");return serialize(item)
@router.post("/exceptions/{exception_id}/comments",status_code=201)
def add_comment(exception_id:str,p:Comment,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    ex=db.exceptions.find_one({"_id":ObjectId(exception_id)})
    if not ex:raise HTTPException(404,"Exception not found")
    item={"exception_id":ex["_id"],"loan_id":ex["loan_id"],"author_id":user["_id"],"body":p.body,"created_at":datetime.now(timezone.utc)};item["_id"]=db.exception_comments.insert_one(item).inserted_id;audit(db,"REVIEW_COMMENT_ADDED",user,ex["loan_id"],"Reviewer comment added.");return serialize(item)
@router.get("/exceptions/{exception_id}/comments")
def comments(exception_id:str,user=Depends(require_roles("DATA_OPERATOR","REVIEWER","ADMIN")),db=Depends(get_db)):
    return [serialize(x) for x in db.exception_comments.find({"exception_id":ObjectId(exception_id)}).sort("created_at",1)]
@router.get("/loans/{loan_id}")
def loan_detail(loan_id:str,user=Depends(require_roles("DATA_OPERATOR","REVIEWER","DATA_CONSUMER","ADMIN")),db=Depends(get_db)):
    loan=db.loans.find_one({"loan_id":loan_id})
    if not loan:raise HTTPException(404,"Loan not found")
    return serialize({"loan":loan,"validation_results":list(db.validation_results.find({"loan_document_id":loan["_id"]})),"exceptions":list(db.exceptions.find({"loan_document_id":loan["_id"]}))})
@router.post("/exceptions/{exception_id}/ai-review",status_code=201)
def ai_review(exception_id:str,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    ex=db.exceptions.find_one({"_id":ObjectId(exception_id)})
    if not ex:raise HTTPException(404,"Exception not found")
    s=get_settings()
    if not s.groq_api_key:raise HTTPException(503,"Groq is not configured. Set GROQ_API_KEY on the backend.")
    loan=db.loans.find_one({"_id":ex["loan_document_id"]});prompt=f"Return ONLY JSON with severity, explanation, suggested_field, suggested_value, confidence, reasoning. Explain this exception; do not approve a loan. Exception: {serialize(ex)} Loan: {serialize(loan)}"
    try:
        from groq import Groq
        result=json.loads(Groq(api_key=s.groq_api_key).chat.completions.create(model=s.groq_model,messages=[{"role":"system","content":"You are a conservative loan data quality assistant. Never approve records."},{"role":"user","content":prompt}],response_format={"type":"json_object"}).choices[0].message.content)
    except Exception as err:raise HTTPException(502,"Groq review failed") from err
    review={"exception_id":ex["_id"],"loan_id":ex["loan_id"],"provider":"groq","model":s.groq_model,"request_type":"EXPLAIN_AND_SUGGEST","prompt_summary":ex["description"],"response":result,"created_at":datetime.now(timezone.utc),"requested_by":user["_id"]};review["_id"]=db.ai_reviews.insert_one(review).inserted_id;audit(db,"AI_RECOMMENDATION_GENERATED",user,ex["loan_id"],"AI recommendation generated.",metadata={"ai_review_id":str(review["_id"])});return serialize(review)
@router.post("/exceptions/{exception_id}/decision",status_code=201)
def decide(exception_id:str,p:Decision,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    if p.decision not in {"ACCEPT","EDIT","REJECT"}:raise HTTPException(422,"Decision must be ACCEPT, EDIT, or REJECT")
    ex=db.exceptions.find_one({"_id":ObjectId(exception_id)})
    if not ex:raise HTTPException(404,"Exception not found")
    loan=db.loans.find_one({"_id":ex["loan_document_id"]});old=loan.get(p.field) if p.field else None;item={"exception_id":ex["_id"],"loan_id":ex["loan_id"],"reviewer_id":user["_id"],"decision":p.decision,"field":p.field,"original_value":old,"final_value":p.final_value,"comment":p.comment,"created_at":datetime.now(timezone.utc)};item["_id"]=db.review_decisions.insert_one(item).inserted_id
    if p.decision in {"ACCEPT","EDIT"} and p.field:db.loans.update_one({"_id":loan["_id"]},{"$set":{p.field:p.final_value,"updated_at":datetime.now(timezone.utc)}})
    db.exceptions.update_one({"_id":ex["_id"]},{"$set":{"status":"REJECTED" if p.decision=="REJECT" else "CORRECTED","updated_at":datetime.now(timezone.utc)}});audit(db,"LOAN_REJECTED" if p.decision=="REJECT" else "FIELD_EDITED",user,ex["loan_id"],"Human review decision recorded.",old,p.final_value);return serialize(item)
@router.post("/exceptions/{exception_id}/verify",status_code=201)
def verify(exception_id:str,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    ex=db.exceptions.find_one({"_id":ObjectId(exception_id)})
    if not ex:raise HTTPException(404,"Exception not found")
    if ex["status"] not in {"CORRECTED","REJECTED"}:raise HTTPException(409,"A human decision is required before verification")
    loan=db.loans.find_one({"_id":ex["loan_document_id"]});canonical={k:v for k,v in loan.items() if k not in {"_id","raw_csv_row","upload_id","created_at","updated_at"}};validations=list(db.validation_results.find({"loan_document_id":loan["_id"]}));quality=max(0,100-sum(15 if x["severity"]=="HIGH" else 7 for x in validations));record={"loan_id":loan["loan_id"],"canonical_data":canonical,"record_hash":canonical_hash(canonical),"source_upload_id":loan["upload_id"],"validation_snapshot":validations,"review_decisions":list(db.review_decisions.find({"loan_id":loan["loan_id"]})),"verified_by":user["_id"],"verification_timestamp":datetime.now(timezone.utc),"quality_score":quality,"status":"VERIFIED"};record["_id"]=db.verified_loans.insert_one(record).inserted_id;audit(db,"VERIFIED_RECORD_CREATED",user,loan["loan_id"],"Verified record created.",metadata={"record_hash":record["record_hash"]});return serialize(record)
@router.get("/verified-records")
def verified_records(user=Depends(require_roles("DATA_CONSUMER","REVIEWER","ADMIN")),db=Depends(get_db)):
    return [serialize(x) for x in db.verified_loans.find().sort("verification_timestamp",-1).limit(200)]
@router.get("/verified-records/export")
def export_verified(user=Depends(require_roles("DATA_CONSUMER","REVIEWER","ADMIN")),db=Depends(get_db)):
    records=list(db.verified_loans.find().sort("verification_timestamp",-1)); output=StringIO(); columns=sorted({k for r in records for k in r.get("canonical_data",{})}); writer=csv.DictWriter(output,fieldnames=["loan_id","record_hash","quality_score",*columns]);writer.writeheader()
    for r in records:writer.writerow({"loan_id":r["loan_id"],"record_hash":r["record_hash"],"quality_score":r.get("quality_score",100),**serialize(r.get("canonical_data",{}))})
    audit(db,"VERIFIED_RECORD_EXPORTED",user,None,"Verified records exported.");return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=verified_loans.csv"})
@router.get("/audit/{loan_id}")
def audit_timeline(loan_id:str,user=Depends(require_roles("DATA_CONSUMER","REVIEWER","ADMIN")),db=Depends(get_db)):
    return [serialize(x) for x in db.audit_logs.find({"loan_id":loan_id}).sort("timestamp",1)]
@router.get("/dashboard")
def dashboard(user=Depends(require_roles("DATA_OPERATOR","REVIEWER","DATA_CONSUMER","ADMIN")),db=Depends(get_db)):
    total=db.loans.count_documents({});exceptions=db.exceptions.count_documents({});return {"total_loans":total,"exceptions":exceptions,"high_severity":db.exceptions.count_documents({"severity":"HIGH","status":{"$in":["OPEN","UNDER_REVIEW"]}}),"pending_review":db.exceptions.count_documents({"status":{"$in":["OPEN","UNDER_REVIEW"]}}),"verified_records":db.verified_loans.count_documents({}),"quality_score":round(max(0,100-(exceptions/total*100 if total else 0)),1)}
