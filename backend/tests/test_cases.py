def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


def test_create_and_list_case(client):
    resp = client.post("/api/v1/cases", json={"title": "Case A", "description": "first"})
    assert resp.status_code == 201
    created = resp.json()["data"]
    assert created["title"] == "Case A"
    assert created["id"]

    resp = client.get("/api/v1/cases")
    assert resp.status_code == 200
    titles = [c["title"] for c in resp.json()["data"]]
    assert "Case A" in titles


def test_case_not_found_error_envelope(client):
    resp = client.get("/api/v1/cases/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "CASE_NOT_FOUND"


def test_validation_error_envelope(client):
    resp = client.post("/api/v1/cases", json={"description": "missing title"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_session_lifecycle(client):
    case_id = client.post("/api/v1/cases", json={"title": "Case B"}).json()["data"]["id"]

    resp = client.post(f"/api/v1/cases/{case_id}/sessions", json={"title": "Session 1"})
    assert resp.status_code == 201
    session = resp.json()["data"]
    assert session["status"] == "CREATED"
    assert session["case_id"] == case_id

    resp = client.get(f"/api/v1/cases/{case_id}/sessions")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


def test_session_on_missing_case(client):
    resp = client.post("/api/v1/cases/missing/sessions", json={"title": "x"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CASE_NOT_FOUND"
