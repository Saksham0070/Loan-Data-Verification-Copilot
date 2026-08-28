import hashlib,json,re
from datetime import datetime,timezone
from io import BytesIO
import pandas as pd
from fastapi import HTTPException
from pathlib import Path
from .utils import serialize
from .validators import RULE_DEFINITIONS,validate_loan
def now():return datetime.now(timezone.utc)
def audit(db,event,user,loan_id,detail,old_value=None,new_value=None,metadata=None):db.audit_logs.insert_one({"event_type":event,"timestamp":now(),"user_id":user.get("_id") if user else None,"loan_id":loan_id,"action_detail":detail,"old_value":old_value,"new_value":new_value,"metadata":metadata or {}})
QUALITY_PENALTIES={"HIGH":15,"MEDIUM":7,"LOW":3}
def quality_from_failures(failures):
    """Score only failed checks; passed historical validation records have no penalty."""
    penalty=sum(QUALITY_PENALTIES.get(item.get("severity"),3) for item in failures if not item.get("passed",False))
    return max(0,100-penalty)
HEADER_ALIASES={"loan id":"loan_id","loan number":"loan_id","borrower id":"borrower_id","borrower number":"borrower_id","original principal":"original_principal","original loan amount":"original_principal","loan amount":"original_principal","current balance":"current_balance","outstanding balance":"current_balance","payment status":"payment_status","borrower state":"borrower_state","state":"borrower_state","document status":"document_status","origination date":"origination_date","loan origination date":"origination_date","maturity date":"maturity_date","interest rate":"interest_rate","term months":"term_months","days past due":"days_past_due","last payment date":"last_payment_date","last updated at":"last_updated_at","source system":"source_system"}
NUMERIC_FIELDS={"original_principal","current_balance","interest_rate","term_months","days_past_due","employment_length"}
INTEGER_FIELDS={"term_months","days_past_due"}
DATE_FIELDS={"origination_date","maturity_date","last_payment_date","last_updated_at"}
UPPERCASE_FIELDS={"loan_id","borrower_id","payment_status","borrower_state","document_status","loan_type","credit_grade","source_system"}
MISSING_MARKERS={"","na","n/a","null","none","nan","-"}

def _canonical_header(header):
    cleaned=re.sub(r"[_\-/]+"," ",str(header).strip().lower())
    cleaned=re.sub(r"\s+"," ",cleaned)
    return HEADER_ALIASES.get(cleaned,cleaned.replace(" ","_"))

def _is_missing(value):
    if value is None:return True
    if isinstance(value,str):return value.strip().lower() in MISSING_MARKERS
    try:return bool(pd.isna(value))
    except (TypeError,ValueError):return False

def _normalize_value(field,value):
    if _is_missing(value):return None
    if isinstance(value,str):value=value.strip()
    if field in NUMERIC_FIELDS and isinstance(value,str):
        try:value=float(re.sub(r"[$,%\s,]","",value))
        except ValueError:return value
    if field in INTEGER_FIELDS and isinstance(value,float) and value.is_integer():return int(value)
    if field in DATE_FIELDS and isinstance(value,str):
        try:
            parsed=pd.to_datetime(value,errors="coerce")
            if not pd.isna(parsed):return parsed.date().isoformat()
        except (TypeError,ValueError):pass
    if field in UPPERCASE_FIELDS and isinstance(value,str):return value.upper()
    return value

def normalize_with_lineage(row):
    """Return canonical data plus an evidence log; never mutate the raw source row."""
    normalized={};changes=[]
    for raw_field,raw_value in row.items():
        field=_canonical_header(raw_field);value=_normalize_value(field,raw_value);normalized[field]=value
        source_value=None if _is_missing(raw_value) else raw_value
        if str(raw_field)!=field or source_value!=value:
            changes.append({"raw_field":str(raw_field),"canonical_field":field,"raw_value":source_value,"normalized_value":value})
    return normalized,changes

def normalize_row(row):
    """Compatibility helper used by secondary-source imports."""
    return normalize_with_lineage(row)[0]
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
            raw={str(k):(None if pd.isna(v) else (v.item() if hasattr(v,"item") else v)) for k,v in s.to_dict().items()};loan,normalization_changes=normalize_with_lineage(raw);lid=str(loan.get("loan_id") or "");dup=lid in seen or (bool(lid) and bool(db.loans.find_one({"loan_id":lid})));combo={"borrower_id":loan.get("borrower_id"),"original_principal":loan.get("original_principal"),"origination_date":loan.get("origination_date")};duplicate_borrower=all(v not in (None,"") for v in combo.values()) and bool(db.loans.find_one(combo));seen.add(lid);normalized_at=now();loan.update({"upload_id":uid,"source_row_number":row_number,"raw_csv_row":raw,"normalization_metadata":{"version":"1.0","normalized_at":normalized_at,"changes":normalization_changes},"source_system":loan.get("source_system") or "CSV_UPLOAD","ingestion_source_type":"CSV_UPLOAD","created_at":normalized_at,"updated_at":normalized_at});docid=db.loans.insert_one(loan).inserted_id;audit(db,"LOAN_NORMALIZED",user,lid,"Raw CSV row normalized into the canonical loan schema.",metadata={"source_row_number":row_number,"normalization_version":"1.0","changes":normalization_changes});audit(db,"LOAN_IMPORTED",user,lid,"Loan row imported from CSV.")
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
