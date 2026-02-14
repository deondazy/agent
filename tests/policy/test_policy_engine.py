from openclaw_agent.policy.engine import PolicyEngine


def test_rejects_disallowed_command() -> None:
    policy = PolicyEngine()
    decision = policy.evaluate_command("rm -rf /")

    assert decision.allowed is False
    assert decision.reason == "blocked_by_policy"


def test_requires_approval_for_privileged_command() -> None:
    policy = PolicyEngine()
    decision = policy.evaluate_command("sudo apt-get update")

    assert decision.allowed is False
    assert decision.requires_approval is True


def test_allows_approved_privileged_command() -> None:
    policy = PolicyEngine()
    decision = policy.evaluate_command("sudo apt-get update", approval_token="approve-1")

    assert decision.allowed is True
