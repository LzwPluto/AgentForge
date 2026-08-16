import pytest
from fastapi.testclient import TestClient
from gui.server import app, shared_memory, orchestrator
from config import config

client = TestClient(app)

def test_get_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "AgentForge" in response.text

def test_get_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "workflow_state" in data
    assert "agent_states" in data
    assert "tasks" in data
    assert "config" in data

def test_get_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "agent_slots" in data

def test_update_config():
    cfg = config.model_dump()
    cfg["max_loops_per_task"] = 12
    response = client.post("/api/config", json=cfg)
    assert response.status_code == 200
    assert response.json()["config"]["max_loops_per_task"] == 12

def test_get_history():
    response = client.get("/api/history")
    assert response.status_code == 200
    assert "sessions" in response.json()

def test_get_files():
    response = client.get("/api/files")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "items" in data

def test_sandbox_check():
    response = client.get("/api/sandbox/check")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data

def test_diff_api():
    response = client.get("/api/diff")
    assert response.status_code == 200
    data = response.json()
    assert "diff" in data

def test_websocket_init():
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data["event_type"] == "INIT_STATE"
        assert "config" in data["data"]
        
        # Test ping pong
        websocket.send_json({"command": "PING"})
        pong = websocket.receive_json()
        assert pong["event_type"] == "PONG"

def test_plugins_api():
    response = client.get("/api/plugins")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["plugins"]) >= 3
    
    # Test toggle
    p_id = data["plugins"][0]["id"]
    orig_enabled = data["plugins"][0]["enabled"]
    toggle_res = client.post(f"/api/plugins/{p_id}/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["plugin"]["enabled"] == (not orig_enabled)
    
    # Toggle back
    toggle_back = client.post(f"/api/plugins/{p_id}/toggle")
    assert toggle_back.json()["plugin"]["enabled"] == orig_enabled

