from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "ai-file-search"


def test_api_status():
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "database" in data
    assert "watcher" in data
    assert "indexed_files" in data


def test_api_search_validation():
    # Empty query should fail validation
    res = client.post("/api/search", json={"query": ""})
    assert res.status_code == 422

    # Disallowed extension should fail validation
    res = client.post("/api/search", json={"query": "test", "extensions": [".exe"]})
    assert res.status_code == 422

    # Valid query
    res = client.post("/api/search", json={"query": "keamanan jaringan", "top_k": 3})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "keamanan jaringan"
    assert "took_ms" in data
    assert isinstance(data["results"], list)


def test_api_files_extension_validation():
    # Disallowed extension should return 400
    res = client.get("/api/files?extension=.exe")
    assert res.status_code == 400

    # Allowed extension should return 200
    res = client.get("/api/files?extension=.pdf")
    assert res.status_code == 200


def test_settings_page_html():
    res = client.get("/settings")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Pengaturan & Diagnostik" in res.text

