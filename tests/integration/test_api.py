from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sip.api.app import create_app
from sip.config import Settings

DECIDER = {"X-User-Id": "d1", "X-User-Name": "Dana Decider", "X-User-Roles": "decision_maker"}
PRIVACY = {"X-User-Id": "p1", "X-User-Roles": "privacy_reviewer"}
GOV = {"X-User-Id": "g1", "X-User-Roles": "governance_reviewer"}
VIEWER = {"X-User-Roles": "viewer"}


def wait(c: TestClient, iid: str) -> dict[str, Any]:
    for _ in range(300):
        st = c.get(f"/api/investigations/{iid}").json()
        if st["summary"]["status"] != "running":
            return st
        time.sleep(0.05)
    raise AssertionError("timed out")


@pytest.fixture
def client(settings: Settings):  # type: ignore[no-untyped-def]
    with TestClient(create_app(settings)) as c:
        yield c


def test_end_to_end_review_flow_with_rbac(client: TestClient) -> None:
    assert client.post("/api/investigations", json={"scenario_id": "northstar"}, headers=VIEWER).status_code == 403
    iid = client.post("/api/investigations", json={"scenario_id": "northstar"}).json()["id"]
    assert client.post(f"/api/investigations/{iid}/start").status_code == 200
    assert client.post(f"/api/investigations/{iid}/start").status_code == 409
    st = wait(client, iid)
    assert st["summary"]["status"] == "awaiting_review"
    rid = st["pending_review_id"]
    url = f"/api/investigations/{iid}/reviews/{rid}/respond"
    assert client.post(url, json={"action": "approve"}, headers=GOV).status_code == 403  # privacy role required
    assert client.post(url, json={"action": "decide"}, headers=PRIVACY).status_code == 422
    # The body cannot impersonate someone else: unknown fields are rejected, actor comes from auth.
    assert client.post(url, json={"action": "approve", "actor": {"kind": "agent"}}, headers=PRIVACY).status_code == 422
    assert client.post(url, json={"action": "approve", "note": "ok per Jane Smith"}, headers=PRIVACY).status_code == 200
    st = wait(client, iid)
    privacy = next(r for r in st["reviews"] if r["kind"] == "privacy_release")
    assert privacy["response"]["actor"]["id"] == "dev:p1" and "Jane Smith" not in privacy["response"]["note"]

    rid = st["pending_review_id"]
    assert (
        client.post(
            f"/api/investigations/{iid}/reviews/{rid}/respond", json={"action": "approve"}, headers=GOV
        ).status_code
        == 200
    )
    st = wait(client, iid)
    assert st["summary"]["status"] == "awaiting_decision"
    review = next(r for r in st["reviews"] if r["id"] == st["pending_review_id"])
    url = f"/api/investigations/{iid}/reviews/{review['id']}/respond"
    decision = {
        "decision_type": "adopt_option",
        "statement": "Redesign DTS",
        "rationale": "Evidence",
        "option_ids": [review["context"]["options"][0]["id"]],
        "uncertainties_acknowledged": True,
    }
    assert client.post(url, json={"action": "decide", "decision": decision}, headers=GOV).status_code == 403
    assert client.post(url, json={"action": "decide", "decision": decision}, headers=DECIDER).status_code == 200
    st = wait(client, iid)
    assert st["summary"]["status"] == "decided"
    assert st["decision"]["decided_by"]["display_name"] == "Dana Decider"

    claim = next(c for c in st["claims"] if c["causal"] and c["classification"] == "inferred")
    chain = client.get(f"/api/investigations/{iid}/claims/{claim['id']}").json()
    assert chain["evidence"] and chain["sources"]
    src = client.get(f"/api/investigations/{iid}/sources/{chain['sources'][0]['id']}").json()
    assert src["content"]
    audit = client.get(f"/api/investigations/{iid}/audit").json()
    assert any(a["action"] == "decision_recorded" and a["actor_id"] == "dev:d1" for a in audit)


def test_invalid_decision_is_refused_and_review_stays_pending(client: TestClient) -> None:
    iid = client.post("/api/investigations", json={"scenario_id": "northstar"}).json()["id"]
    client.post(f"/api/investigations/{iid}/start")
    st = wait(client, iid)
    while st["summary"]["status"] == "awaiting_review":
        client.post(f"/api/investigations/{iid}/reviews/{st['pending_review_id']}/respond", json={"action": "approve"})
        st = wait(client, iid)
    rid = st["pending_review_id"]
    bad = {"decision_type": "defer", "statement": "s", "rationale": "r", "uncertainties_acknowledged": False}
    client.post(f"/api/investigations/{iid}/reviews/{rid}/respond", json={"action": "decide", "decision": bad})
    st = wait(client, iid)
    assert st["summary"]["status"] == "awaiting_decision" and st["decision"] is None


def test_upload_goes_through_privacy_gateway(client: TestClient) -> None:
    iid = client.post(
        "/api/investigations", json={"question": "Why has customer churn increased at Acme?", "organisation": "Acme"}
    ).json()["id"]
    r = client.post(
        f"/api/investigations/{iid}/documents",
        files={"file": ("notes.txt", b"Spoke with Jane Smith (jane@acme.example). Churn rose.")},
        data={"source_type": "crm_record", "confidentiality": "internal"},
    )
    assert r.status_code == 201
    doc = r.json()
    assert "Jane" not in doc["sanitised_preview"] and doc["scan"]["classification"]["personal_data"] == "personal"
    full = client.get(f"/api/investigations/{iid}/documents/{doc['id']}").json()
    assert "jane@acme.example" not in full["sanitised_text"]
    bad = client.post(f"/api/investigations/{iid}/documents", files={"file": ("x.exe", b"MZ")})
    assert bad.status_code == 415


def test_dev_auth_is_refused_in_production(settings: Settings) -> None:
    with pytest.raises(RuntimeError):
        create_app(settings.model_copy(update={"sip_env": "production"}))


def test_scenarios_hidden_by_default(settings: Settings) -> None:
    with TestClient(create_app(settings.model_copy(update={"sip_show_scenarios": False}))) as c:
        assert c.get("/api/scenarios").json() == []
        assert c.post("/api/investigations", json={"scenario_id": "northstar"}).status_code == 400
