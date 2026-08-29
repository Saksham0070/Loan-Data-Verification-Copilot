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
from ..validators import RULE_DEFINITIONS

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
    safe_limit=min(max(limit,1),100);safe_offset=max(offset,0)
    if upload.get("source_type") in {"SERVICER_UPDATE","DOCUMENT_MANIFEST"}:
        query={"upload_id":upload_object_id}
        if search:query["loan_id"]={"$regex":search,"$options":"i"}
        total=db.source_records.count_documents(query)
        items=list(db.source_records.find(query).sort("source_row_number",1).skip(safe_offset).limit(safe_limit))
        return serialize({"upload":{"_id":upload["_id"],"filename":upload.get("filename"),"source_type":upload.get("source_type"),"uploaded_at":upload.get("uploaded_at"),"rows_total":upload.get("rows_total")},"record_kind":"SOURCE_EVIDENCE","items":items,"pagination":{"total":total,"limit":safe_limit,"offset":safe_offset,"has_more":safe_offset+len(items)<total}})
    query={"upload_id":upload_object_id}
    if status:query["aggregate_status"]=status
    if search:query["$or"]=[{"loan_id":{"$regex":search,"$options":"i"}},{"borrower_id":{"$regex":search,"$options":"i"}}]
    total=db.loans.count_documents(query);items=list(db.loans.find(query,{"raw_csv_row":0,"normalization_metadata":0}).sort("source_row_number",1).skip(safe_offset).limit(safe_limit))
    return serialize({"upload":{"_id":upload["_id"],"filename":upload.get("filename"),"source_type":upload.get("source_type"),"uploaded_at":upload.get("uploaded_at"),"rows_total":upload.get("rows_total")},"record_kind":"CANONICAL_LOAN","items":items,"pagination":{"total":total,"limit":safe_limit,"offset":safe_offset,"has_more":safe_offset+len(items)<total}})

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

def _model_json_object(model_text):
    """Extract a JSON object while discarding accidental model reasoning text."""
    candidate=(model_text or "").strip().replace("```json","").replace("```","").strip()
    start,end=candidate.find("{"),candidate.rfind("}")
    if start<0 or end<=start:return None
    try:return json.loads(candidate[start:end+1])
    except (ValueError,json.JSONDecodeError):return None

def _fallback_batch_summary(exceptions):
    """Return a clear summary even when an AI provider returns malformed JSON."""
    groups={}
    for exception in exceptions:
        key=(exception.get("title") or exception.get("rule_name") or "Data-quality issue",exception.get("severity","MEDIUM"))
        groups.setdefault(key,[]).append(exception.get("loan_id") or "Unidentified loan")
    issue_groups=[{"issue_type":title,"severity":severity,"affected_loan_ids":loan_ids,"what_it_means":"This record needs a reviewer check before it can be trusted.","recommended_reviewer_action":"Open the affected record, compare its source evidence, and correct or request a correction."} for (title,severity),loan_ids in groups.items()]
    has_high=any(group["severity"]=="HIGH" for group in issue_groups)
    return {"overall_assessment":f"This batch has {len(exceptions)} open data-quality issue{'s' if len(exceptions)!=1 else ''}. {'High-priority items should be reviewed first.' if has_high else 'The issues need normal reviewer follow-up.'}","risk_level":"HIGH" if has_high else "MEDIUM","priority_actions":[{"priority":1,"action":"Review high-priority records first.","why":"They can prevent a loan record from being verified.","affected_loan_ids":[loan for group in issue_groups if group["severity"]=="HIGH" for loan in group["affected_loan_ids"]]}],"issue_groups":issue_groups,"reviewer_note":"Use this summary to plan review work. Confirm every decision against the stored source evidence.","human_control_notice":"AI only summarizes issues. A reviewer must approve, edit, reject, or request correction; it cannot change loan data."}

def _structured_batch_summary(model_text,exceptions):
    """Accept only a compact, reviewer-focused model payload; otherwise use fallback."""
    payload=_model_json_object(model_text)
    if not isinstance(payload,dict) or not isinstance(payload.get("issue_groups"),list):
        return _fallback_batch_summary(exceptions)
    fallback=_fallback_batch_summary(exceptions)
    risk=str(payload.get("risk_level",fallback["risk_level"]).upper())
    risk=risk if risk in {"HIGH","MEDIUM","LOW"} else fallback["risk_level"]
    groups=[]
    for group in payload["issue_groups"][:10]:
        if not isinstance(group,dict):continue
        groups.append({"issue_type":str(group.get("issue_type") or "Data-quality issue"),"severity":str(group.get("severity") or "MEDIUM").upper(),"affected_loan_ids":[str(loan) for loan in group.get("affected_loan_ids",[])[:20]],"what_it_means":str(group.get("what_it_means") or "This record needs a reviewer check."),"recommended_reviewer_action":str(group.get("recommended_reviewer_action") or "Review the source evidence and make a human decision.")})
    if not groups:return fallback
    actions=[]
    for action in payload.get("priority_actions",[])[:5]:
        if not isinstance(action,dict):continue
        actions.append({"priority":action.get("priority",len(actions)+1),"action":str(action.get("action") or "Review the affected records."),"why":str(action.get("why") or "This helps resolve the batch safely."),"affected_loan_ids":[str(loan) for loan in action.get("affected_loan_ids",[])[:20]]})
    return {"overall_assessment":str(payload.get("overall_assessment") or fallback["overall_assessment"]),"risk_level":risk,"priority_actions":actions or fallback["priority_actions"],"issue_groups":groups,"reviewer_note":str(payload.get("reviewer_note") or fallback["reviewer_note"]),"human_control_notice":"AI only summarizes issues. A reviewer must approve, edit, reject, or request correction; it cannot change loan data."}

def _existing_rule_guidance(rule_id,description):
    rule=RULE_DEFINITIONS[rule_id]
    return {"plain_language_interpretation":f"Good news: this request is already covered by the existing '{rule.rule_name}' check. {rule.description}","is_rule_recommended":False,"existing_rule":{"rule_id":rule.rule_id,"name":rule.rule_name,"severity":rule.severity,"description":rule.description},"recommended_next_step":"Use the existing exception queue to review the affected loan, compare its source evidence, then correct, reject, or request correction as appropriate.","proposed_rule":None,"test_cases":[],"reviewer_note":"No new development work is needed for this request. The current validation rule already checks it."}

def _fallback_rule_proposal(description):
    """Give useful business guidance even when an AI provider omits valid JSON."""
    text=description.lower()
    existing_rules=[
        (("closed" in text and "balance" in text),"CLOSED_LOAN_POSITIVE_BALANCE"),
        (("balance" in text and "principal" in text),"BALANCE_NOT_EXCEEDS_PRINCIPAL"),
        (("negative" in text and "balance" in text),"NO_NEGATIVE_BALANCE"),
        (("negative" in text and ("principal" in text or "amount" in text)),"NO_NEGATIVE_PRINCIPAL"),
        (("duplicate" in text and "loan" in text),"DUPLICATE_LOAN_ID"),
        (("document" in text),"REQUIRED_DOCUMENT_STATUS"),
        (("state" in text),"INVALID_STATE_CODE"),
        (("date" in text),"VALID_DATES"),
        (("interest" in text or "rate" in text),"INTEREST_RATE_RANGE"),
        (("past due" in text or "delinquent" in text),"PAYMENT_STATUS_CONSISTENCY"),
        (("missing" in text or "required" in text),"REQUIRED_FIELDS_PRESENT"),
    ]
    for matches,rule_id in existing_rules:
        if matches:return _existing_rule_guidance(rule_id,description)
    if "flag" in text or "check" in text or "validate" in text:
        return {"plain_language_interpretation":"This looks like a new condition the review system may need to check.","is_rule_recommended":True,"existing_rule":None,"recommended_next_step":"Confirm the exact field values and business threshold with the product owner before a developer adds this rule.","proposed_rule":{"name":"Proposed custom data-quality check","rule_id":"PROPOSED_CUSTOM_RULE","description":"A proposed rule based on the reviewer request. It must be approved before implementation.","severity":"MEDIUM","fields":["Confirm affected loan field"],"condition":description},"test_cases":[{"scenario":"Record meets the requested condition","sample_input":"A loan record matching the condition above.","expected_result":"Create an exception for reviewer review."},{"scenario":"Record does not meet the requested condition","sample_input":"A loan record outside the condition above.","expected_result":"Allow the record to continue through validation."}],"reviewer_note":"This is a draft proposal. Confirm the business definition and expected severity before implementing it."}
    return {"plain_language_interpretation":f"You asked: {description}","is_rule_recommended":False,"existing_rule":None,"recommended_next_step":"Describe the loan field, the condition that should be flagged, and why it matters. For example: Flag active loans with more than 90 days past due.","proposed_rule":None,"test_cases":[],"reviewer_note":"This is a proposal only. A developer and business reviewer must approve any new validation rule before it is added to the system."}

def _structured_rule_proposal(model_text,description):
    """Convert a model response into safe UI data; never expose its reasoning text."""
    payload=_model_json_object(model_text)
    fallback=_fallback_rule_proposal(description)
    if not isinstance(payload,dict):return fallback
    recommended=payload.get("is_rule_recommended") is True
    raw_rule=payload.get("proposed_rule") if isinstance(payload.get("proposed_rule"),dict) else None
    if recommended and not raw_rule:recommended=False
    rule=None
    if raw_rule:
        fields=raw_rule.get("fields",[])
        rule={"name":str(raw_rule.get("name") or "Proposed validation rule"),"rule_id":str(raw_rule.get("rule_id") or "PROPOSED_RULE"),"description":str(raw_rule.get("description") or "Review this proposed rule before implementation."),"severity":str(raw_rule.get("severity") or "MEDIUM").upper(),"fields":[str(field) for field in fields[:10]] if isinstance(fields,list) else [],"condition":str(raw_rule.get("condition") or "No condition provided.")}
    tests=[]
    raw_tests=payload.get("test_cases",[])
    if isinstance(raw_tests,list):
        for test in raw_tests[:5]:
            if isinstance(test,dict):tests.append({"scenario":str(test.get("scenario") or "Test scenario"),"sample_input":str(test.get("sample_input") or "Example record"),"expected_result":str(test.get("expected_result") or "Expected outcome")})
    return {"plain_language_interpretation":str(payload.get("plain_language_interpretation") or fallback["plain_language_interpretation"]),"is_rule_recommended":recommended,"existing_rule":fallback.get("existing_rule") if not recommended else None,"recommended_next_step":str(payload.get("recommended_next_step") or fallback["recommended_next_step"]),"proposed_rule":rule if recommended else None,"test_cases":tests if recommended else [],"reviewer_note":str(payload.get("reviewer_note") or fallback["reviewer_note"])}

def _groq_or_503():
    from ..config import get_settings
    s=get_settings()
    if not s.groq_api_key:raise HTTPException(503,"Groq is not configured")
    return s

@router.post("/ai/batch-summary")
def batch_summary(payload:BatchRequest,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    s=_groq_or_503(); exceptions=[serialize(x) for x in db.exceptions.find({"_id":{"$in":[ObjectId(x) for x in payload.exception_ids]}})];system_prompt="You are a loan data-review assistant for non-technical reviewers. Return ONLY valid JSON. Never include markdown, XML tags, or reasoning steps. Do not approve records or change data. Use plain business language and this exact shape: {overall_assessment: string, risk_level: HIGH|MEDIUM|LOW, priority_actions: [{priority: number, action: string, why: string, affected_loan_ids: string[]}], issue_groups: [{issue_type: string, severity: HIGH|MEDIUM|LOW, affected_loan_ids: string[], what_it_means: string, recommended_reviewer_action: string}], reviewer_note: string}."
    try:
        from groq import Groq
        text=Groq(api_key=s.groq_api_key).chat.completions.create(model=s.groq_model,messages=[{"role":"system","content":system_prompt},{"role":"user","content":json.dumps(exceptions)}]).choices[0].message.content
    except Exception as exc:raise HTTPException(502,"Groq request failed") from exc
    summary=_structured_batch_summary(text,exceptions);created_at=datetime.now(timezone.utc);audit(db,"AI_BATCH_SUMMARY_GENERATED",user,None,"AI batch exception summary generated; no loan data was changed.",metadata={"provider":"groq","model":s.groq_model,"exception_count":len(exceptions),"prompt_summary":"Plain-language batch exception summary","risk_level":summary["risk_level"]});return {"summary":summary,"exception_count":len(exceptions),"provider":"groq","model":s.groq_model,"created_at":created_at,"prompt_summary":"Plain-language batch exception summary"}

@router.post("/ai/generate-rule")
def generate_rule(payload:NaturalLanguageRule,user=Depends(require_roles("REVIEWER","ADMIN")),db=Depends(get_db)):
    s=_groq_or_503();system_prompt="You help non-technical loan-data reviewers assess a request for a possible validation rule. Return ONLY valid JSON. Never include markdown, XML tags, or reasoning steps. Do not change data or code. Use this exact shape: {plain_language_interpretation: string, is_rule_recommended: boolean, recommended_next_step: string, proposed_rule: {name: string, rule_id: string, description: string, severity: HIGH|MEDIUM|LOW, fields: string[], condition: string} | null, test_cases: [{scenario: string, sample_input: string, expected_result: string}], reviewer_note: string}. If the request is a question or not a clear rule, set is_rule_recommended to false, proposed_rule to null, and answer in plain language."
    try:
        from groq import Groq
        text=Groq(api_key=s.groq_api_key).chat.completions.create(model=s.groq_model,messages=[{"role":"system","content":system_prompt},{"role":"user","content":payload.description}]).choices[0].message.content
    except Exception as exc:raise HTTPException(502,"Groq request failed") from exc
    proposal=_structured_rule_proposal(text,payload.description);created_at=datetime.now(timezone.utc);audit(db,"AI_RULE_SUGGESTION_GENERATED",user,None,"AI validation-rule suggestion generated; no rule or data was changed.",metadata={"provider":"groq","model":s.groq_model,"prompt_summary":payload.description,"is_rule_recommended":proposal["is_rule_recommended"]});return {"proposal":proposal,"provider":"groq","model":s.groq_model,"created_at":created_at,"prompt_summary":payload.description}
