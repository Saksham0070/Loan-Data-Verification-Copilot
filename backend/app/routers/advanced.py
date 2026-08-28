"""Supplementary judging APIs: exact resource routes and multi-source ingestion."""
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import pandas as pd
from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from ..database import get_db
from ..security import require_roles
from ..services import audit, normalize_row, quality_from_failures
from ..utils import serialize

router=APIRouter(tags=["Records, sources, and AI utilities"])

def _exception(db, loan, rule_id, title, description, fields, user):
    result={"loan_id":loan["loan_id"],"loan_document_id":loan["_id"],"upload_id":loan.get("upload_id"),"rule_id":rule_id,"rule_name":title,"severity":"HIGH","passed":False,"message":description,"affected_fields":fields,"actual_values":{},"timestamp":datetime.now(timezone.utc)}
    rid=db.validation_results.insert_one(result).inserted_id
    db.exceptions.insert_one({"loan_id":loan["loan_id"],"loan_document_id":loan["_id"],"validation_result_id":rid,"rule_id":rule_id,"severity":"HIGH","status":"OPEN","title":title,"description":description,"affected_fields":fields,"created_at":datetime.now(timezone.utc),"updated_at":datetime.now(timezone.utc)})
    audit(db,"EXCEPTION_CREATED",user,loan["loan_id"],description)

@router.get("/loans")
def list_loans(limit:int=100,loan_id:str|None=None,borrower_id:str|None=None,user=Depends(require_roles("DATA_OPERATOR","REVIEWER","DATA_CONSUMER","ADMIN")),db=Depends(get_db)):
    q={k:v for k,v in {"loan_id":loan_id,"borrower_id":borrower_id}.items() if v};return [serialize(x) for x in db.loans.find(q,{"raw_csv_row":0}).sort("created_at",-1).limit(min(limit,500))]

@router.get("/uploads/{upload_id}/records")
def batch_records(upload_id:str,limit:int=20,offset:int=0,status:str|None=None,search:str|None=None,user=Depends(require_roles("DATA_OPERATOR","REVIEWER","DATA_CONSUMER","ADMIN")),db=Depends(get_db)):
    try:upload_object_id=ObjectId(upload_id)
    except Exception as exc:raise HTTPException(422,"Invalid upload ID") from exc
    upload=db.uploads.find_one({"_id":upload_object_id})
    if not upload:raise HTTPException(404,"Upload not found")
    query={"upload_id":upload_object_id}
    if status:query["aggregate_status"]=status
    if search:query["$or"]=[{"loan_id":{"$regex":search,"$options":"i"}},{"borrower_id":{"$regex":search,"$options":"i"}}]
    safe_limit=min(max(limit,1),100);safe_offset=max(offset,0);total=db.loans.count_documents(query);items=list(db.loans.find(query,{"raw_csv_row":0,"normalization_metadata":0}).sort("source_row_number",1).skip(safe_offset).limit(safe_limit))
    return serialize({"upload":{"_id":upload["_id"],"filename":upload.get("filename"),"source_type":upload.get("source_type"),"uploaded_at":upload.get("uploaded_at"),"rows_total":upload.get("rows_total")},"items":items,"pagination":{"total":total,"limit":safe_limit,"offset":safe_offset,"has_more":safe_offset+len(items)<total}})

@router.get("/uploads/{upload_id}/exceptions")
def batch_exceptions(upload_id:str,limit:int=50,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    """Return a reviewable batch slice for the AI summary workbench."""
    try:upload_object_id=ObjectId(upload_id)
    except Exception as exc:raise HTTPException(422,"Invalid upload ID") from exc
    loan_ids=[item["_id"] for item in db.loans.find({"upload_id":upload_object_id},{"_id":1})]
    if not loan_ids:return []
    return [serialize(item) for item in db.exceptions.find({"loan_document_id":{"$in":loan_ids},"status":{"$in":["OPEN","UNDER_REVIEW","CORRECTION_REQUESTED"]}}).sort("created_at",-1).limit(min(max(limit,1),50))]

@router.get("/verified-loans")
def verified_loans(user=Depends(require_roles("DATA_CONSUMER","REVIEWER","ADMIN")),db=Depends(get_db)):
    return [serialize(x) for x in db.verified_loans.find().sort("verification_timestamp",-1).limit(200)]

@router.get("/verified-loans/{record_id}")
def verified_loan(record_id:str,user=Depends(require_roles("DATA_CONSUMER","REVIEWER","ADMIN")),db=Depends(get_db)):
    record=db.verified_loans.find_one({"_id":ObjectId(record_id)})
    if not record:raise HTTPException(404,"Verified record not found")
    return serialize(record)

@router.get("/summary")
def summary(user=Depends(require_roles("DATA_OPERATOR","REVIEWER","DATA_CONSUMER","ADMIN")),db=Depends(get_db)):
    loans=list(db.loans.find({}, {"_id":1}));total=len(loans);exceptions=db.exceptions.count_documents({});active=list(db.exceptions.find({"status":{"$in":["OPEN","UNDER_REVIEW","CORRECTION_REQUESTED"]}}));by_loan={str(loan["_id"]):[] for loan in loans}
    for item in active:by_loan.setdefault(str(item.get("loan_document_id")),[]).append(item)
    quality=round(sum(quality_from_failures(by_loan.get(str(loan["_id"]),[])) for loan in loans)/total,1) if total else 100.0
    return {"total_loans":total,"exceptions":exceptions,"open_exceptions":len(active),"verified_loans":db.verified_loans.count_documents({}),"quality_score":quality}

@router.get("/ai/status")
def ai_status(user=Depends(require_roles("DATA_OPERATOR","REVIEWER","DATA_CONSUMER","ADMIN"))):
    """Return readiness/model metadata without exposing the Groq API key."""
    from ..config import get_settings
    settings=get_settings()
    return {"provider":"groq","model":settings.groq_model,"enabled":bool(settings.groq_api_key)}

@router.get("/dashboard/activity")
def dashboard_activity(user=Depends(require_roles("DATA_OPERATOR","REVIEWER","DATA_CONSUMER","ADMIN")),db=Depends(get_db)):
    active_statuses=["OPEN","UNDER_REVIEW","CORRECTION_REQUESTED"]
    return serialize({"recent_uploads":list(db.uploads.find().sort("uploaded_at",-1).limit(5)),"recent_exceptions":list(db.exceptions.find().sort("created_at",-1).limit(5)),"recent_verifications":list(db.verified_loans.find().sort("verification_timestamp",-1).limit(5)),"severity_breakdown":{"HIGH":db.exceptions.count_documents({"severity":"HIGH","status":{"$in":active_statuses}}),"MEDIUM":db.exceptions.count_documents({"severity":"MEDIUM","status":{"$in":active_statuses}}),"CORRECTION_REQUESTED":db.exceptions.count_documents({"status":"CORRECTION_REQUESTED"})}})

@router.get("/validation-rules")
def rules(user=Depends(require_roles("DATA_OPERATOR","REVIEWER","ADMIN"))):
    path=Path(__file__).resolve().parents[3]/"data"/"validation_rules.json"
    return json.loads(path.read_text(encoding="utf-8"))

@router.post("/uploads/secondary",status_code=201)
async def secondary_upload(source_type:str, file:UploadFile=File(...), user=Depends(require_roles("DATA_OPERATOR","ADMIN")),db=Depends(get_db)):
    if source_type not in {"SERVICER_UPDATE","DOCUMENT_MANIFEST"}:raise HTTPException(422,"source_type must be SERVICER_UPDATE or DOCUMENT_MANIFEST")
    try: frame=pd.read_csv(BytesIO(await file.read()))
    except Exception as exc:raise HTTPException(422,"Unable to parse CSV") from exc
    upload={"filename":file.filename,"uploaded_by":user["_id"],"uploaded_at":datetime.now(timezone.utc),"status":"COMPLETED","source_type":source_type,"rows_total":len(frame),"rows_success":0,"rows_failed":0,"validation_status":"COMPLETED"};upload["_id"]=db.uploads.insert_one(upload).inserted_id; conflicts=0
    for source_row_number,(_,series) in enumerate(frame.iterrows(),start=1):
        row=normalize_row({str(k):(None if pd.isna(v) else (v.item() if hasattr(v,"item") else v)) for k,v in series.to_dict().items()});loan_id=str(row.get("loan_id") or "");db.source_records.insert_one({"upload_id":upload["_id"],"source_type":source_type,"loan_id":loan_id,"source_row_number":source_row_number,"raw_row":row,"created_at":datetime.now(timezone.utc)})
        loan=db.loans.find_one({"loan_id":loan_id})
        if loan:
            fields=("document_status",) if source_type=="DOCUMENT_MANIFEST" else ("current_balance","payment_status","last_updated_at")
            changed=[f for f in fields if row.get(f) not in (None,"") and loan.get(f) not in (None,"") and row[f]!=loan[f]]
            if changed:_exception(db,loan,"CONFLICTING_VALUES","Conflicting source values","A secondary source conflicts with the original loan tape.",changed,user);conflicts+=1
        upload["rows_success"]+=1
    db.uploads.update_one({"_id":upload["_id"]},{"$set":{"rows_success":upload["rows_success"],"rows_failed":conflicts}});audit(db,"FILE_UPLOADED",user,None,f"{source_type} file uploaded.",metadata={"upload_id":str(upload["_id"]),"conflicts":conflicts});return serialize({**upload,"rows_failed":conflicts,"conflicts_created":conflicts})

class BatchRequest(BaseModel): exception_ids:list[str]=Field(min_length=1,max_length=50)
class NaturalLanguageRule(BaseModel): description:str=Field(min_length=10,max_length=1000)

def _groq_or_503():
    from ..config import get_settings
    s=get_settings()
    if not s.groq_api_key:raise HTTPException(503,"Groq is not configured")
    return s

@router.post("/ai/batch-summary")
def batch_summary(payload:BatchRequest,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    s=_groq_or_503(); exceptions=[serialize(x) for x in db.exceptions.find({"_id":{"$in":[ObjectId(x) for x in payload.exception_ids]}})];system_prompt="Summarize loan data-quality exceptions. Do not approve records."
    try:
        from groq import Groq
        text=Groq(api_key=s.groq_api_key).chat.completions.create(model=s.groq_model,messages=[{"role":"system","content":system_prompt},{"role":"user","content":json.dumps(exceptions)}]).choices[0].message.content
    except Exception as exc:raise HTTPException(502,"Groq request failed") from exc
    created_at=datetime.now(timezone.utc);audit(db,"AI_BATCH_SUMMARY_GENERATED",user,None,"AI batch exception summary generated; no loan data was changed.",metadata={"provider":"groq","model":s.groq_model,"exception_count":len(exceptions),"prompt_summary":"Batch exception summary"});return {"summary":text,"exception_count":len(exceptions),"provider":"groq","model":s.groq_model,"created_at":created_at,"prompt_summary":"Batch exception summary"}

@router.post("/ai/generate-rule")
def generate_rule(payload:NaturalLanguageRule,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    s=_groq_or_503();system_prompt="Return a proposed JSON validation rule and pytest test outline. This is a suggestion only; do not change data or code."
    try:
        from groq import Groq
        text=Groq(api_key=s.groq_api_key).chat.completions.create(model=s.groq_model,messages=[{"role":"system","content":system_prompt},{"role":"user","content":payload.description}]).choices[0].message.content
    except Exception as exc:raise HTTPException(502,"Groq request failed") from exc
    created_at=datetime.now(timezone.utc);audit(db,"AI_RULE_SUGGESTION_GENERATED",user,None,"AI validation-rule suggestion generated; no rule or data was changed.",metadata={"provider":"groq","model":s.groq_model,"prompt_summary":payload.description});return {"proposal":text,"provider":"groq","model":s.groq_model,"created_at":created_at,"prompt_summary":payload.description}
