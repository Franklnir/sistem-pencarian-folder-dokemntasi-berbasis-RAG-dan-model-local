import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_llm_status_endpoint():
    response = client.get("/api/llm/status")
    assert response.status_code == 200
    data = response.json()
    assert "library_installed" in data
    assert data["library_installed"] is True
    assert "model_exists" in data
    assert data["model_exists"] is True
    assert "model_size_mb" in data
    assert data["model_size_mb"] > 400


def test_llm_models_catalog_endpoint():
    response = client.get("/api/llm/models")
    assert response.status_code == 200
    models = response.json()
    assert isinstance(models, list)
    assert len(models) >= 2
    filenames = [m["filename"] for m in models]
    assert "qwen2.5-0.5b-instruct-q4_k_m.gguf" in filenames
    assert "qwen2.5-1.5b-instruct-q4_k_m.gguf" in filenames


def test_llm_chat_ask_missing_query():
    # Query must be at least 2 chars
    response = client.post("/api/chat/ask", json={"query": "a"})
    assert response.status_code == 422
