from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .database import create_database,ensure_indexes
from .routers import advanced,auth,feedback,uploads,workflow
@asynccontextmanager
async def lifespan(app):
    app.state.db=create_database()
    if app.state.db is not None:
        try:ensure_indexes(app.state.db)
        except Exception:pass
    yield
s=get_settings();app=FastAPI(title="Loan Data Verification Copilot API",version="1.0.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in s.cors_origins.split(",") if x.strip()],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.get("/")
def root():return {"service":"Loan Data Verification Copilot API","status":"ok","docs":"/docs","health":"/health"}
@app.get("/health")
def health():return {"status":"ok","service":"loan-data-verification-copilot"}
for router in (auth.router,uploads.router,workflow.router,advanced.router,feedback.router):app.include_router(router,prefix="/api")
