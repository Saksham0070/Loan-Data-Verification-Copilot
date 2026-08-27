from datetime import date,datetime
VALID_STATUSES={"ACTIVE","CURRENT","DELINQUENT","CLOSED","DEFAULTED","PAID_OFF"};VALID_STATES={"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","IA","ID","IL","IN","KS","KY","LA","MA","MD","ME","MI","MN","MO","MS","MT","NC","ND","NE","NH","NJ","NM","NV","NY","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VA","VT","WA","WI","WV","WY","DC"};REQUIRED=("loan_id","borrower_id","origination_date","maturity_date","original_principal","current_balance","payment_status","borrower_state","document_status")
def issue(i,n,s,m,f,v):return {"rule_id":i,"rule_name":n,"severity":s,"passed":False,"message":m,"affected_fields":f,"actual_values":v}
def parse_date(v):
    if isinstance(v,date):return v
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00")).date() if v else None
    except ValueError:return None
def validate_loan(loan,duplicate=False,duplicate_borrower_record=False):
    f=[];missing=[x for x in REQUIRED if loan.get(x) in (None,"")]
    if missing:f.append(issue("REQUIRED_FIELDS_PRESENT","Required Fields Present","HIGH","Required fields are missing.",missing,{x:loan.get(x) for x in missing}))
    o,m=parse_date(loan.get("origination_date")),parse_date(loan.get("maturity_date"))
    if not o or not m:f.append(issue("VALID_DATES","Valid Dates","HIGH","Origination and maturity dates must be valid ISO dates.",["origination_date","maturity_date"],{}))
    elif m<=o:f.append(issue("MATURITY_AFTER_ORIGINATION","Maturity After Origination","HIGH","Maturity date must be after origination date.",["origination_date","maturity_date"],{}))
    p,b=loan.get("original_principal"),loan.get("current_balance")
    if not isinstance(p,(int,float)) or not isinstance(b,(int,float)):f.append(issue("VALID_NUMERIC_VALUES","Valid Numeric Values","HIGH","Principal and balance must be numeric.",["original_principal","current_balance"],{"original_principal":p,"current_balance":b}))
    else:
        if p<0:f.append(issue("NO_NEGATIVE_PRINCIPAL","No Negative Principal","HIGH","Original principal cannot be negative.",["original_principal"],{"original_principal":p}))
        if b<0:f.append(issue("NO_NEGATIVE_BALANCE","No Negative Balance","HIGH","Current balance cannot be negative.",["current_balance"],{"current_balance":b}))
        if b>p:f.append(issue("BALANCE_NOT_EXCEEDS_PRINCIPAL","Balance Not Greater Than Principal","HIGH","Current balance exceeds original principal.",["current_balance","original_principal"],{"current_balance":b,"original_principal":p}))
        if loan.get("payment_status")=="CLOSED" and b>0:f.append(issue("CLOSED_LOAN_POSITIVE_BALANCE","Closed Loan Positive Balance","MEDIUM","A closed loan has a positive balance.",["payment_status","current_balance"],{"current_balance":b}))
    rate=loan.get("interest_rate")
    if isinstance(rate,(int,float)) and not 0<=rate<=100:f.append(issue("INTEREST_RATE_RANGE","Interest Rate Range","MEDIUM","Interest rate must be between 0 and 100 percent.",["interest_rate"],{"interest_rate":rate}))
    if loan.get("payment_status") and loan["payment_status"] not in VALID_STATUSES:f.append(issue("VALID_PAYMENT_STATUS","Valid Payment Status","MEDIUM","Payment status is not recognized.",["payment_status"],{}))
    if loan.get("borrower_state") and loan["borrower_state"] not in VALID_STATES:f.append(issue("INVALID_STATE_CODE","Valid State Code","MEDIUM","Borrower state must be a two-letter US state code.",["borrower_state"],{}))
    if loan.get("document_status") not in (None,"COMPLETE"):f.append(issue("REQUIRED_DOCUMENT_STATUS","Required Document Status","MEDIUM","Document status must be COMPLETE.",["document_status"],{}))
    if loan.get("payment_status") in {"DEFAULTED","DELINQUENT"} and isinstance(loan.get("days_past_due"),(int,float)) and loan["days_past_due"]<=0:f.append(issue("PAYMENT_STATUS_CONSISTENCY","Payment Status Consistency","MEDIUM","Delinquent/defaulted status requires days past due greater than zero.",["payment_status","days_past_due"],{}))
    if loan.get("payment_status") in {"ACTIVE","CURRENT"} and isinstance(b,(int,float)) and b==0:f.append(issue("CONFLICTING_VALUES","Conflicting Values","MEDIUM","An active/current loan has a zero balance.",["payment_status","current_balance"],{}))
    updated=parse_date(loan.get("last_updated_at"))
    if updated and (date.today()-updated).days>180:f.append(issue("STALE_RECORD","Stale Record","MEDIUM","Record has not been updated in over 180 days.",["last_updated_at"],{"last_updated_at":str(updated)}))
    if duplicate:f.append(issue("DUPLICATE_LOAN_ID","Duplicate Loan ID","HIGH","Loan ID is duplicated in this upload or a prior upload.",["loan_id"],{"loan_id":loan.get("loan_id")}))
    if duplicate_borrower_record:f.append(issue("SUSPICIOUS_DUPLICATE_BORROWER","Suspicious Duplicate Borrower","MEDIUM","Borrower, original principal, and origination date match an existing record.",["borrower_id","original_principal","origination_date"],{"borrower_id":loan.get("borrower_id")}))
    return f
