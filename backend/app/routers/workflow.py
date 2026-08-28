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
from ..services import audit,canonical_hash,configured_results,quality_from_failures,revalidate_loan
from ..validators import validate_loan
from ..utils import serialize
router=APIRouter(tags=["Review workflow"])
EDITABLE_LOAN_FIELDS={"borrower_id","loan_type","origination_date","maturity_date","original_principal","current_balance","interest_rate","term_months","borrower_state","loan_purpose","credit_grade","employment_length","income_band","payment_status","days_past_due","servicer_name","last_payment_date","last_updated_at","document_status","source_system"}
class Decision(BaseModel):
    decision:str
    field:str|None=None
    final_value:object|None=None
    comment:str=Field(min_length=1)
    ai_review_id:str|None=None
class Comment(BaseModel):body:str=Field(min_length=1,max_length=2000)
@router.get("/exceptions")
def queue(status:str|None=None,severity:str|None=None,search:str|None=None,user=Depends(require_roles("DATA_OPERATOR","REVIEWER","ADMIN")),db=Depends(get_db)):
    q={k:v for k,v in {"status":status,"severity":severity}.items() if v}
    if search:
        loan_matches=list(db.loans.find({"$or":[{"loan_id":{"$regex":search,"$options":"i"}},{"borrower_id":{"$regex":search,"$options":"i"}}]},{"loan_id":1}))
        q["loan_id"]={"$in":[x.get("loan_id","") for x in loan_matches]}
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
    return serialize({"loan":loan,"validation_results":list(db.validation_results.find({"loan_document_id":loan["_id"]})),"exceptions":list(db.exceptions.find({"loan_document_id":loan["_id"]})),"ai_reviews":list(db.ai_reviews.find({"loan_id":loan_id})),"review_decisions":list(db.review_decisions.find({"loan_id":loan_id})),"verified_records":list(db.verified_loans.find({"loan_id":loan_id})),"audit_events":list(db.audit_logs.find({"loan_id":loan_id}).sort("timestamp",1))})
@router.post("/exceptions/{exception_id}/ai-review",status_code=201)
def ai_review(exception_id:str,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    ex=db.exceptions.find_one({"_id":ObjectId(exception_id)})
    if not ex:raise HTTPException(404,"Exception not found")
    s=get_settings()
    if not s.groq_api_key:raise HTTPException(503,"Groq is not configured. Set GROQ_API_KEY on the backend.")
    loan=db.loans.find_one({"_id":ex["loan_document_id"]});system_prompt="You are a conservative loan data quality assistant. Never approve records or change loan data. Return recommendations for a human reviewer only.";prompt=f"Return ONLY JSON with severity, explanation, suggested_field, suggested_value, confidence, reasoning. Explain this exception; do not approve a loan. Exception: {serialize(ex)} Loan: {serialize(loan)}";audit(db,"AI_REVIEW_REQUESTED",user,ex["loan_id"],"Reviewer requested an AI explanation.",metadata={"exception_id":exception_id,"provider":"groq","model":s.groq_model,"prompt_summary":ex["description"]})
    try:
        from groq import Groq
        result=json.loads(Groq(api_key=s.groq_api_key).chat.completions.create(model=s.groq_model,messages=[{"role":"system","content":system_prompt},{"role":"user","content":prompt}],response_format={"type":"json_object"}).choices[0].message.content)
    except Exception as err:
        # Do not leak provider keys or prompts, but return enough context for a
        # local demo user to distinguish model/configuration failures.
        raise HTTPException(502,f"Groq review failed ({type(err).__name__}). Check GROQ_MODEL and your Groq project permissions.") from err
    review={"exception_id":ex["_id"],"loan_id":ex["loan_id"],"provider":"groq","model":s.groq_model,"request_type":"EXPLAIN_AND_SUGGEST","system_instruction":system_prompt,"prompt":prompt,"prompt_summary":ex["description"],"response":result,"created_at":datetime.now(timezone.utc),"requested_by":user["_id"]};review["_id"]=db.ai_reviews.insert_one(review).inserted_id;audit(db,"AI_RECOMMENDATION_GENERATED",user,ex["loan_id"],"AI recommendation generated; no loan data was changed.",metadata={"ai_review_id":str(review["_id"]),"provider":"groq","model":s.groq_model,"prompt_summary":review["prompt_summary"],"suggested_field":result.get("suggested_field"),"suggested_value":result.get("suggested_value"),"confidence":result.get("confidence")});return serialize(review)
@router.post("/exceptions/{exception_id}/decision",status_code=201)
def decide(exception_id:str,p:Decision,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    if p.decision not in {"ACCEPT","EDIT","REJECT"}:raise HTTPException(422,"Decision must be ACCEPT, EDIT, or REJECT")
    ex=db.exceptions.find_one({"_id":ObjectId(exception_id)})
    if not ex:raise HTTPException(404,"Exception not found")
    ai_review=None
    if p.decision=="ACCEPT":
        if not p.ai_review_id:raise HTTPException(422,"Accepting a suggestion requires ai_review_id")
        try:ai_review=db.ai_reviews.find_one({"_id":ObjectId(p.ai_review_id),"exception_id":ex["_id"]})
        except Exception as err:raise HTTPException(422,"ai_review_id is invalid") from err
        if not ai_review:raise HTTPException(422,"AI recommendation does not belong to this exception")
        suggestion=ai_review.get("response") or {};p.field=suggestion.get("suggested_field");p.final_value=suggestion.get("suggested_value")
        if p.field not in EDITABLE_LOAN_FIELDS or p.final_value is None:raise HTTPException(422,"The AI recommendation has no safe editable field/value; use Edit or Reject")
    elif p.decision=="EDIT":
        if p.field not in EDITABLE_LOAN_FIELDS or p.final_value is None:raise HTTPException(422,"Edit requires an allowed field and a final value")
    loan=db.loans.find_one({"_id":ex["loan_document_id"]});old=loan.get(p.field) if p.field else None;item={"exception_id":ex["_id"],"loan_id":ex["loan_id"],"reviewer_id":user["_id"],"decision":p.decision,"field":p.field,"original_value":old,"final_value":p.final_value,"comment":p.comment,"ai_review_id":ai_review.get("_id") if ai_review else None,"created_at":datetime.now(timezone.utc)};item["_id"]=db.review_decisions.insert_one(item).inserted_id
    if p.decision in {"ACCEPT","EDIT"}:db.loans.update_one({"_id":loan["_id"]},{"$set":{p.field:p.final_value,"updated_at":datetime.now(timezone.utc)}})
    db.exceptions.update_one({"_id":ex["_id"]},{"$set":{"status":"REJECTED" if p.decision=="REJECT" else "CORRECTED","updated_at":datetime.now(timezone.utc)}});event="AI_RECOMMENDATION_ACCEPTED" if p.decision=="ACCEPT" else ("LOAN_REJECTED" if p.decision=="REJECT" else "FIELD_EDITED");audit(db,event,user,ex["loan_id"],"Human review decision recorded.",old,p.final_value,metadata={"decision_id":str(item["_id"]),"decision":p.decision,"ai_review_id":str(ai_review["_id"]) if ai_review else None,"human_comment":p.comment})
    post_edit_validation=None
    if p.decision in {"ACCEPT","EDIT"}:post_edit_validation=revalidate_loan(db,db.loans.find_one({"_id":loan["_id"]}),user,"Reviewer correction")
    return serialize({**item,"post_edit_validation":post_edit_validation})
@router.post("/exceptions/{exception_id}/verify",status_code=201)
def verify(exception_id:str,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    ex=db.exceptions.find_one({"_id":ObjectId(exception_id)})
    if not ex:raise HTTPException(404,"Exception not found")
    loan=db.loans.find_one({"_id":ex["loan_document_id"]})
    if db.verified_loans.find_one({"loan_document_id":loan["_id"]}):raise HTTPException(409,"This loan version already has a verified record")
    loan_exceptions=list(db.exceptions.find({"loan_document_id":loan["_id"]}))
    blocked=[item for item in loan_exceptions if item.get("status") in {"OPEN","UNDER_REVIEW"}]
    rejected=[item for item in loan_exceptions if item.get("status")=="REJECTED"]
    if blocked:raise HTTPException(409,"Resolve every open exception before verification")
    if rejected:raise HTTPException(409,"A rejected loan cannot be made into a verified record")
    duplicate=bool(db.loans.find_one({"loan_id":loan.get("loan_id"),"_id":{"$ne":loan["_id"]}}));combo={"borrower_id":loan.get("borrower_id"),"original_principal":loan.get("original_principal"),"origination_date":loan.get("origination_date"),"_id":{"$ne":loan["_id"]}};duplicate_borrower=all(loan.get(key) not in (None,"") for key in ("borrower_id","original_principal","origination_date")) and bool(db.loans.find_one(combo));final_failures=configured_results(validate_loan(loan,duplicate,duplicate_borrower));audit(db,"FINAL_VALIDATION_EXECUTED",user,loan["loan_id"],"Final validation executed before verification.",metadata={"failed_rules":[item["rule_id"] for item in final_failures]})
    if final_failures:raise HTTPException(409,"Final validation still has failed checks; correct the record before verification")
    canonical={k:v for k,v in loan.items() if k not in {"_id","raw_csv_row","upload_id","created_at","updated_at","normalization_metadata"}};record={"loan_id":loan["loan_id"],"loan_document_id":loan["_id"],"canonical_data":canonical,"record_hash":canonical_hash(canonical),"source_upload_id":loan["upload_id"],"validation_snapshot":{"final_validation":"PASSED","failed_rules":[],"quality_score":quality_from_failures(final_failures)},"review_decisions":list(db.review_decisions.find({"loan_id":loan["loan_id"]})),"verified_by":user["_id"],"verification_timestamp":datetime.now(timezone.utc),"quality_score":quality_from_failures(final_failures),"status":"VERIFIED"};record["_id"]=db.verified_loans.insert_one(record).inserted_id;db.loans.update_one({"_id":loan["_id"]},{"$set":{"aggregate_status":"VERIFIED","verified_record_id":record["_id"],"updated_at":datetime.now(timezone.utc)}});audit(db,"VERIFIED_RECORD_CREATED",user,loan["loan_id"],"Verified record created.",metadata={"record_hash":record["record_hash"],"quality_score":record["quality_score"]});return serialize(record)
@router.get("/verified-records")
def verified_records(user=Depends(require_roles("DATA_CONSUMER","REVIEWER","ADMIN")),db=Depends(get_db)):
    return [serialize(x) for x in db.verified_loans.find().sort("verification_timestamp",-1).limit(200)]
@router.get("/verified-records/export")
def export_verified(user=Depends(require_roles("DATA_CONSUMER","REVIEWER","ADMIN")),db=Depends(get_db)):
    records=list(db.verified_loans.find().sort("verification_timestamp",-1)); output=StringIO(); columns=sorted({k for r in records for k in r.get("canonical_data",{})}); writer=csv.DictWriter(output,fieldnames=["loan_id","record_hash","quality_score",*columns]);writer.writeheader()
    for r in records:writer.writerow({"loan_id":r["loan_id"],"record_hash":r["record_hash"],"quality_score":r.get("quality_score",100),**serialize(r.get("canonical_data",{}))})
    audit(db,"VERIFIED_RECORD_EXPORTED",user,None,"Verified records exported.");return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=verified_loans.csv"})
@router.get("/audit/{loan_id}")
def audit_timeline(loan_id:str,user=Depends(require_roles("DATA_OPERATOR","DATA_CONSUMER","REVIEWER","ADMIN")),db=Depends(get_db)):
    return [serialize(x) for x in db.audit_logs.find({"loan_id":loan_id}).sort("timestamp",1)]
@router.get("/dashboard")
def dashboard(user=Depends(require_roles("DATA_OPERATOR","REVIEWER","DATA_CONSUMER","ADMIN")),db=Depends(get_db)):
    loans=list(db.loans.find({}, {"_id":1}));total=len(loans);exceptions=db.exceptions.count_documents({});active=list(db.exceptions.find({"status":{"$in":["OPEN","UNDER_REVIEW"]}}));by_loan={str(loan["_id"]):[] for loan in loans}
    for item in active:by_loan.setdefault(str(item.get("loan_document_id")),[]).append(item)
    quality_score=round(sum(quality_from_failures(by_loan.get(str(loan["_id"]),[])) for loan in loans)/total,1) if total else 100.0
    return {"total_loans":total,"exceptions":exceptions,"high_severity":db.exceptions.count_documents({"severity":"HIGH","status":{"$in":["OPEN","UNDER_REVIEW"]}}),"pending_review":len(active),"verified_records":db.verified_loans.count_documents({}),"quality_score":quality_score}
