from pathlib import Path

from denosysbot.skills.engine import (
    create_skill_file,
    load_skills,
    match_skills,
    render_skill_context,
    update_skill_file,
)


def test_create_skill_file_writes_frontmatter_and_body(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    created = create_skill_file(
        skills_dir=skills_dir,
        name="deploy-docker",
        description="Deploy apps with Docker Compose",
        triggers=("docker", "compose", "deploy"),
    )

    assert created == skills_dir / "deploy-docker.md"
    text = created.read_text()
    assert text.startswith("---\n")
    assert "name: deploy-docker" in text
    assert "description: Deploy apps with Docker Compose" in text
    assert "triggers: docker,compose,deploy" in text
    assert "Workflow" in text


def test_load_and_match_skills_returns_relevant_entries(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    create_skill_file(
        skills_dir=skills_dir,
        name="deploy-docker",
        description="Deploy apps with Docker Compose",
        triggers=("docker", "compose", "deploy"),
    )
    create_skill_file(
        skills_dir=skills_dir,
        name="run-tests",
        description="Run and interpret pytest suites",
        triggers=("test", "pytest"),
    )

    loaded = load_skills(skills_dir)
    matched = match_skills("Need help deploying with docker compose", loaded)

    assert len(loaded) == 2
    assert len(matched) == 1
    assert matched[0].name == "deploy-docker"


def test_render_skill_context_includes_skill_text(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    create_skill_file(
        skills_dir=skills_dir,
        name="api-errors",
        description="Handle API error responses",
        triggers=("api", "errors"),
    )
    matched = match_skills("API errors are failing in prod", load_skills(skills_dir))
    context = render_skill_context(matched)

    assert "Relevant local skills:" in context
    assert "api-errors" in context
    assert "Handle API error responses" in context


def test_update_skill_file_updates_frontmatter_fields(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    create_skill_file(
        skills_dir=skills_dir,
        name="deploy-docker",
        description="Deploy apps with Docker Compose",
        triggers=("docker", "compose", "deploy"),
    )

    updated_path = update_skill_file(
        skills_dir=skills_dir,
        name="deploy-docker",
        description="Deploy services with Kubernetes",
        triggers=("kubernetes", "helm", "deploy"),
    )
    loaded = load_skills(skills_dir)

    assert updated_path == skills_dir / "deploy-docker.md"
    assert len(loaded) == 1
    assert loaded[0].name == "deploy-docker"
    assert loaded[0].description == "Deploy services with Kubernetes"
    assert loaded[0].triggers == ("kubernetes", "helm", "deploy")


def test_load_skills_skips_markdown_with_invalid_frontmatter_schema(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "broken.md").write_text(
        (
            "---\n"
            "name: broken-skill\n"
            "description: Broken skill without required triggers\n"
            "extra: invalid\n"
            "---\n\n"
            "Body text.\n"
        )
    )

    loaded = load_skills(skills_dir)

    assert loaded == []
