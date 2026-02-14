def test_create_run_returns_run_id(client) -> None:
    payload = {
        "issue_ref": "acme/repo#123",
        "repo_target": "github:acme/repo",
    }

    response = client.post("/runs", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["run_id"]
    assert body["state"] == "queued"


def test_advance_run_moves_state(client) -> None:
    payload = {
        "issue_ref": "acme/repo#42",
        "repo_target": "github:acme/repo",
    }
    create_response = client.post("/runs", json=payload)
    run_id = create_response.json()["run_id"]

    advance_response = client.post(f"/runs/{run_id}/advance")

    assert advance_response.status_code == 200
    assert advance_response.json()["state"] == "ingesting"
