from openclaw_agent.queue.tasks import dispatch_stage


def test_dispatch_stage_invokes_orchestration() -> None:
    result = dispatch_stage("run-1", "ingesting")

    assert result["run_id"] == "run-1"
    assert result["stage"] == "ingesting"
