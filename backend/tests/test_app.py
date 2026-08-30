from app.main import app, health, root

def test_public_health_endpoints():
    assert root()["status"] == "ok"
    assert health()["status"] == "ok"

def test_openapi_includes_judge_required_routes():
    paths=app.openapi()["paths"]
    for path in ["/api/loans","/api/loans/{loan_id}","/api/loans/{loan_id}/verify","/api/uploads/{upload_id}/records","/api/uploads/{upload_id}/exceptions","/api/exceptions","/api/verified-loans","/api/verified-loans/{record_id}","/api/audit/{loan_id}","/api/summary","/api/feedback"]:
        assert path in paths
