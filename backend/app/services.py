import hashlib,json
from datetime import datetime,timezone
from io import BytesIO
import pandas as pd
from fastapi import HTTPException
from pathlib import Path
from .utils import serialize
from .validators import RULE_DEFINITIONS,validate_loan
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
def configured_results(failures):
    """Apply the organizer-visible JSON rule configuration without letting it alter source data."""
    config_path=Path(__file__).resolve().parents[2]/"data"/"validation_rules.json"
    try: config={r["rule_id"]:r for r in json.loads(config_path.read_text(encoding="utf-8"))}
    except (OSError,json.JSONDecodeError): config={}
    filtered=[]
    for failure in failures:
        setting=config.get(failure["rule_id"],{"enabled":True})
        if setting.get("enabled",True):
            failure={**failure,"severity":setting.get("severity",failure["severity"])}
            filtered.append(failure)
    return filtered
def import_csv(db,content,filename,user):
    try:frame=pd.read_csv(BytesIO(content))
    except Exception as exc:raise HTTPException(422,"Unable to parse CSV. Upload a UTF-8 comma-separated file.") from exc
    if frame.empty:raise HTTPException(422,"CSV has no data rows.")
    up={"filename":filename,"uploaded_by":user["_id"],"uploaded_at":now(),"status":"PROCESSING","source_type":"PRIMARY_LOAN_TAPE","rows_total":len(frame),"rows_success":0,"rows_failed":0,"rows_with_exceptions":0,"validation_status":"PROCESSING","failed_rows":[]};uid=db.uploads.insert_one(up).inserted_id;seen=set();count=0;failed_rows=[]
    for row_number,(_,s) in enumerate(frame.iterrows(),start=1):
        # Convert Pandas/Numpy scalar values to standard Python values before
        # storing both the raw source row and normalized record in MongoDB.
        try:
            raw={str(k):(None if pd.isna(v) else (v.item() if hasattr(v,"item") else v)) for k,v in s.to_dict().items()};loan=normalize_row(raw);lid=str(loan.get("loan_id") or "");dup=lid in seen or (bool(lid) and bool(db.loans.find_one({"loan_id":lid})));combo={"borrower_id":loan.get("borrower_id"),"original_principal":loan.get("original_principal"),"origination_date":loan.get("origination_date")};duplicate_borrower=all(v not in (None,"") for v in combo.values()) and bool(db.loans.find_one(combo));seen.add(lid);loan.update({"upload_id":uid,"source_row_number":row_number,"raw_csv_row":raw,"source_system":"CSV_UPLOAD","created_at":now(),"updated_at":now()});docid=db.loans.insert_one(loan).inserted_id;audit(db,"LOAN_IMPORTED",user,lid,"Loan row imported from CSV.")
            failures=configured_results(validate_loan(loan,dup,duplicate_borrower));failed_ids={f["rule_id"] for f in failures}
            evidence=[]
            for rule_id,rule in RULE_DEFINITIONS.items():
                failure=next((x for x in failures if x["rule_id"]==rule_id),None)
                evidence.append({**(failure or {"rule_id":rule_id,"rule_name":rule.rule_name,"severity":rule.severity,"passed":True,"message":"Rule passed.","affected_fields":[],"actual_values":{}}),"loan_id":lid,"loan_document_id":docid,"upload_id":uid,"timestamp":now()})
            ids=db.validation_results.insert_many(evidence).inserted_ids;result_id_by_rule={entry["rule_id"]:ids[index] for index,entry in enumerate(evidence)}
            audit(db,"VALIDATION_EXECUTED",user,lid,"Deterministic validation rules executed.",metadata={"failed_rules":sorted(failed_ids)})
            for failure in failures:
                if failure["severity"] in {"HIGH","MEDIUM"}:
                    db.exceptions.insert_one({"loan_id":lid,"loan_document_id":docid,"validation_result_id":result_id_by_rule[failure["rule_id"]],"rule_id":failure["rule_id"],"severity":failure["severity"],"status":"OPEN","title":failure["rule_name"],"description":failure["message"],"affected_fields":failure["affected_fields"],"created_at":now(),"updated_at":now()});audit(db,"EXCEPTION_CREATED",user,lid,failure["message"],metadata={"rule_id":failure["rule_id"]});count+=1
            if failures:up["rows_with_exceptions"]+=1
            up["rows_success"]+=1
        except Exception as exc:
            failed_rows.append({"row_number":row_number,"error":str(exc),"raw_row":raw if "raw" in locals() else {}})
    up["rows_failed"]=len(failed_rows);up["failed_rows"]=failed_rows
    db.uploads.update_one({"_id":uid},{"$set":{"status":"COMPLETED","validation_status":"COMPLETED","rows_success":up["rows_success"],"rows_failed":up["rows_failed"],"rows_with_exceptions":up["rows_with_exceptions"],"failed_rows":failed_rows}});audit(db,"FILE_UPLOADED",user,None,"CSV uploaded and validation completed.",new_value={"upload_id":str(uid),"exceptions":count,"failed_rows":len(failed_rows)});return serialize({**up,"_id":uid,"status":"COMPLETED","validation_status":"COMPLETED","exceptions_created":count})
def canonical_hash(data):return hashlib.sha256(json.dumps(serialize(data),sort_keys=True,separators=(",",":")).encode()).hexdigest()
