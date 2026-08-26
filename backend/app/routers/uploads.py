from fastapi import APIRouter,Depends,File,HTTPException,UploadFile
from ..database import get_db
from ..security import require_roles
from ..services import import_csv
from ..utils import serialize
router=APIRouter(prefix="/uploads",tags=["Uploads"])
@router.post("",status_code=201)
async def upload_csv(file:UploadFile=File(...),user=Depends(require_roles("DATA_OPERATOR","ADMIN")),db=Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):raise HTTPException(422,"Only CSV files are supported")
    content=await file.read()
    if len(content)>50*1024*1024:raise HTTPException(413,"CSV exceeds the 50 MB limit")
    return import_csv(db,content,file.filename,user)
@router.get("")
def list_uploads(user=Depends(require_roles("DATA_OPERATOR","REVIEWER","ADMIN")),db=Depends(get_db)):return [serialize(x) for x in db.uploads.find().sort("uploaded_at",-1).limit(50)]
