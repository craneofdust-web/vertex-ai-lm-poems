from __future__ import annotations


def _minimal_nodes() -> list[dict]:
    return [
        {
            "node_id": "n1",
            "node_name": "Root Skill",
            "node_tier": "T1",
            "description": "root concept",
            "unlock_condition": "",
            "prerequisite_nodes": [],
            "metadata": {"support_count": 3},
            "citations": [
                {
                    "source_id": "poem-1.md",
                    "source_title": "Poem One",
                    "quote": "the first line",
                    "why": "supports root",
                    "folder_status": "ok",
                }
            ],
        },
        {
            "node_id": "n2",
            "node_name": "Child Skill",
            "node_tier": "T2",
            "description": "child concept",
            "unlock_condition": "learn root",
            "prerequisite_nodes": ["n1"],
            "metadata": {"support_count": 1},
            "citations": [],
        },
    ]


def test_health(api_env):
    client = api_env["client"]
    resp = client.get("/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["pipeline_version"] == "v0.3.1"


def test_graph_empty(api_env):
    client = api_env["client"]
    api_env["ingest_mock_run"]("run_full_empty", [])

    resp = client.get("/graph", params={"run_id": "run_full_empty"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_id"] == "run_full_empty"
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert payload["meta"]["node_count"] == 0
    assert payload["meta"]["edge_count"] == 0


def test_runs_empty(api_env):
    client = api_env["client"]
    resp = client.get("/runs")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["pipeline_version"] == "v0.3.1"
    assert payload["runs"] == []


def test_ingest_and_graph(api_env):
    client = api_env["client"]
    source_folder = api_env["source_folder"]
    (source_folder / "poem-1.md").write_text("the first line\nsecond line", encoding="utf-8")
    api_env["ingest_mock_run"]("run_full_mock", _minimal_nodes(), with_visualization=True)

    graph_resp = client.get("/graph", params={"run_id": "run_full_mock"})
    assert graph_resp.status_code == 200
    graph_payload = graph_resp.json()
    assert graph_payload["meta"]["node_count"] == 2
    assert graph_payload["meta"]["edge_count"] == 1

    runs_resp = client.get("/runs")
    assert runs_resp.status_code == 200
    run_ids = [item["run_id"] for item in runs_resp.json()["runs"]]
    assert "run_full_mock" in run_ids

    node_resp = client.get("/node/n1", params={"run_id": "run_full_mock"})
    assert node_resp.status_code == 200
    node_payload = node_resp.json()
    assert node_payload["node"]["id"] == "n1"
    assert len(node_payload["citations"]) == 1


def test_search(api_env):
    client = api_env["client"]
    source_folder = api_env["source_folder"]
    (source_folder / "poem-1.md").write_text("the first line\nsecond line", encoding="utf-8")
    api_env["ingest_mock_run"]("run_full_search", _minimal_nodes())

    resp = client.get("/search", params={"run_id": "run_full_search", "q": "Child"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_id"] == "run_full_search"
    assert any(node["id"] == "n2" for node in payload["nodes"])


def test_visualization_routes(api_env):
    client = api_env["client"]
    api_env["ingest_mock_run"]("run_full_visual", _minimal_nodes(), with_visualization=True)

    index_resp = client.get("/visualizations")
    assert index_resp.status_code == 200

    latest_resp = client.get("/visualization/latest", params={"mode": "full"}, follow_redirects=False)
    assert latest_resp.status_code == 307
    assert "/visualization/run_full_visual/" in latest_resp.headers["location"]

    run_page = client.get("/visualization/run_full_visual/")
    assert run_page.status_code == 200
