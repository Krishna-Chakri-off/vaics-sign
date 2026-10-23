import os
os.environ["DATABASE_URL"] = "sqlite:///./test_cms.db"
os.environ["WEBHOOKS_ENABLED"] = "false"
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.seed import seed
    seed(reset=True)
    from app.main import app
    with TestClient(app) as c:
        yield c


def login(client, who):
    r = client.post("/api/v1/auth/login", json={"email": f"{who}@vaics.com", "password": "Demo@123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
