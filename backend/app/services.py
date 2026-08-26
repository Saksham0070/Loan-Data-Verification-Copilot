import hashlib,json
from datetime import datetime,timezone
from io import BytesIO
import pandas as pd
from fastapi import HTTPException
from .utils import serialize
from .validators import validate_loan
def now():return datetime.now(timezone.utc)
def audit(db,event,user,loan_id,detail,old_value=None,new_value=None,metadata=None):db.audit_logs.insert_one({"event_type":event,"timestamp":now(),"user_id":user.get("_id") if user else None,"loan_id":loan_id,"action_detail":detail,"old_value":old_value,"new_value":new_value,"metadata":metadata or {}})
def normalize_row(row):
    aliases={"loan id":"loan_id","borrower id":"borrower_id","original principal":"original_principal","current balance":"current_balance","payment status":"payment_status","borrower state":"borrower_state","document status":"document_status","origination date":"origination_date","maturity date":"maturity_date"};out={}
    for k,v in row.items():
        k=aliases.get(str(k).strip().lower(),str(k).strip().lower().replace(" ","_"));v=None if pd.isna(v) else v
        if k in {"original_principal","current_balance","interest_rate","term_months","days_past_due","employment_length"} and v is not None:
            try:v=float(v)
            except (ValueError,TypeError):pass
        if k in {"payment_status","borrower_state","document_status","loan_type","credit_grade"} and isinstance(v,str):v=v.strip().upper()
        out[k]=v
    return out
def import_csv(db,content,filename,user):
    try:frame=pd.read_csv(BytesIO(content))
    except Exception as exc:raise HTTPException(422,"Unable to parse CSV. Upload a UTF-8 comma-separated file.") from exc
    if frame.empty:raise HTTPException(422,"CSV has no data rows.")
    up={"filename":filename,"uploaded_by":user["_id"],"uploaded_at":now(),"status":"PROCESSING","rows_total":len(frame),"rows_success":0,"rows_failed":0,"validation_status":"PROCESSING"};uid=db.uploads.insert_one(up).inserted_id;seen=set();count=0
    for row_number,(_,s) in enumerate(frame.iterrows(),start=1):
        # Convert Pandas/Numpy scalar values to standard Python values before
        # storing both the raw source row and normalized record in MongoDB.
        raw={str(k):(None if pd.isna(v) else (v.item() if hasattr(v,"item") else v)) for k,v in s.to_dict().items()};loan=normalize_row(raw);lid=str(loan.get("loan_id") or "");dup=lid in seen or (bool(lid) and bool(db.loans.find_one({"loan_id":lid})));seen.add(lid);loan.update({"upload_id":uid,"source_row_number":row_number,"raw_csv_row":raw,"created_at":now(),"updated_at":now()});docid=db.loans.insert_one(loan).inserted_id;audit(db,"LOAN_IMPORTED",user,lid,"Loan row imported from CSV.")
        failures=validate_loan(loan,dup)
        borrower_id=loan.get("borrower_id")
        if borrower_id and db.loans.count_documents({"borrower_id":borrower_id})>1:
            failures.append({"rule_id":"SUSPICIOUS_DUPLICATE_BORROWER","rule_name":"Suspicious Duplicate Borrower","severity":"MEDIUM","passed":False,"message":"Borrower appears on multiple imported loan records; reviewer confirmation is required.","affected_fields":["borrower_id"],"actual_values":{"borrower_id":borrower_id}})
        for failure in failures:
            r={**failure,"loan_id":lid,"loan_document_id":docid,"upload_id":uid,"timestamp":now()};rid=db.validation_results.insert_one(r).inserted_id
            if failure["severity"] in {"HIGH","MEDIUM"}:db.exceptions.insert_one({"loan_id":lid,"loan_document_id":docid,"validation_result_id":rid,"rule_id":failure["rule_id"],"severity":failure["severity"],"status":"OPEN","title":failure["rule_name"],"description":failure["message"],"affected_fields":failure["affected_fields"],"created_at":now(),"updated_at":now()});count+=1
        up["rows_success"]+=1
    db.uploads.update_one({"_id":uid},{"$set":{"status":"COMPLETED","validation_status":"COMPLETED","rows_success":up["rows_success"],"rows_failed":count}});audit(db,"FILE_UPLOADED",user,None,"CSV uploaded and validation completed.",new_value={"upload_id":str(uid),"exceptions":count});return serialize({**up,"_id":uid,"status":"COMPLETED","validation_status":"COMPLETED","rows_failed":count,"exceptions_created":count})
def canonical_hash(data):return hashlib.sha256(json.dumps(serialize(data),sort_keys=True,separators=(",",":")).encode()).hexdigest()
