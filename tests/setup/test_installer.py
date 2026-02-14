from openclaw_agent.installer import (
    WalkthroughAnswers,
    build_env_updates,
    merge_env_content,
)


def test_build_env_updates_for_openai_and_anthropic_profile() -> None:
    answers = WalkthroughAnswers(
        profile="openai-anthropic",
        openai_api_key="sk-openai",
        anthropic_api_key="sk-anthropic",
    )

    updates = build_env_updates(answers)

    assert updates["OPENCLAW_MODEL_FALLBACK_ORDER"] == "openai,anthropic"
    assert updates["OPENAI_API_KEY"] == "sk-openai"
    assert updates["ANTHROPIC_API_KEY"] == "sk-anthropic"
    assert "OLLAMA_API_KEY" not in updates


def test_build_env_updates_for_ollama_profile() -> None:
    answers = WalkthroughAnswers(
        profile="ollama-only",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:14b",
    )

    updates = build_env_updates(answers)

    assert updates["OPENCLAW_MODEL_FALLBACK_ORDER"] == "ollama"
    assert updates["OPENCLAW_MODEL_OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert updates["OPENCLAW_MODEL_OLLAMA_MODEL"] == "qwen2.5-coder:14b"


def test_merge_env_content_updates_existing_values_and_preserves_lines() -> None:
    existing = "# existing\nOPENCLAW_MODEL_FALLBACK_ORDER=openai\nFOO=bar\n"
    updates = {
        "OPENCLAW_MODEL_FALLBACK_ORDER": "openai,anthropic,ollama",
        "OPENAI_API_KEY": "sk-test",
    }

    merged = merge_env_content(existing, updates)

    assert "# existing" in merged
    assert "FOO=bar" in merged
    assert "OPENCLAW_MODEL_FALLBACK_ORDER=openai,anthropic,ollama" in merged
    assert "OPENAI_API_KEY=sk-test" in merged
