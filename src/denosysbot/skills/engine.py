"""Markdown skill discovery, creation, and prompt context helpers."""

from dataclasses import dataclass
from pathlib import Path
import re

FRONTMATTER_DELIMITER = "---"
WORD_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")
SKILL_NAME_PATTERN = re.compile(r"[^a-z0-9-]+")
TRIGGER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,}$")
ALLOWED_FRONTMATTER_KEYS = frozenset({"name", "description", "triggers"})


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    name: str
    description: str
    triggers: tuple[str, ...]
    path: Path
    body: str


def create_skill_file(
    skills_dir: Path,
    name: str,
    description: str,
    triggers: tuple[str, ...] = (),
    body: str | None = None,
) -> Path:
    """Create a markdown skill file with minimal frontmatter."""

    normalized_name = _normalize_skill_name(name)
    normalized_description = description.strip() or f"{normalized_name} workflow skill"
    normalized_triggers = _normalize_triggers(triggers, normalized_name, normalized_description)
    skill_body = body.strip() if isinstance(body, str) and body.strip() else _default_skill_body()

    skills_dir.mkdir(parents=True, exist_ok=True)
    path = _resolve_unique_path(skills_dir, normalized_name)
    path.write_text(_render_skill_markdown(normalized_name, normalized_description, normalized_triggers, skill_body))
    return path


def load_skills(skills_dir: Path) -> list[SkillDefinition]:
    """Load all markdown skills from a local directory."""

    if not skills_dir.exists():
        return []

    loaded: list[SkillDefinition] = []
    for skill_path in sorted(skills_dir.rglob("*.md")):
        try:
            text = skill_path.read_text()
        except OSError:
            continue
        metadata, body = _split_frontmatter(text)
        if not _is_valid_frontmatter(metadata):
            continue

        raw_name = metadata["name"].strip()
        raw_description = metadata["description"].strip()
        raw_triggers = _split_csv(metadata["triggers"])
        if not raw_triggers:
            continue

        name = _normalize_skill_name(raw_name)
        if name != raw_name:
            continue
        description = raw_description
        triggers = _normalize_triggers(raw_triggers, name, description)
        if triggers != tuple(raw_triggers):
            continue

        loaded.append(
            SkillDefinition(
                name=name,
                description=description,
                triggers=triggers,
                path=skill_path,
                body=body.strip(),
            )
        )
    return loaded


def update_skill_file(
    skills_dir: Path,
    name: str,
    description: str,
    triggers: tuple[str, ...] = (),
    body: str | None = None,
) -> Path:
    """Update a local skill file in-place, preserving body unless explicitly replaced."""

    normalized_name = _normalize_skill_name(name)
    target_path = skills_dir / f"{normalized_name}.md"
    if not target_path.exists():
        raise FileNotFoundError(f"skill not found: {normalized_name}")

    try:
        existing = target_path.read_text()
    except OSError as exc:  # pragma: no cover - filesystem failures are environment-specific.
        raise FileNotFoundError(f"skill not readable: {normalized_name}") from exc

    metadata, existing_body = _split_frontmatter(existing)
    if not _is_valid_frontmatter(metadata):
        raise ValueError(f"skill has invalid frontmatter: {normalized_name}")

    next_description = description.strip() or metadata["description"].strip()
    next_triggers = _normalize_triggers(
        triggers if triggers else _split_csv(metadata["triggers"]),
        normalized_name,
        next_description,
    )
    next_body = body.strip() if isinstance(body, str) and body.strip() else existing_body.strip()
    if not next_body:
        next_body = _default_skill_body()

    target_path.write_text(
        _render_skill_markdown(
            normalized_name,
            next_description,
            next_triggers,
            next_body,
        )
    )
    return target_path


def match_skills(
    user_message: str,
    skills: list[SkillDefinition],
    *,
    max_matches: int = 3,
) -> list[SkillDefinition]:
    """Rank and return relevant skills for a user message."""

    lowered_message = user_message.lower()
    message_tokens = set(WORD_PATTERN.findall(lowered_message))
    if not message_tokens:
        return []

    scored: list[tuple[int, SkillDefinition]] = []
    for skill in skills:
        score = 0
        if skill.name in lowered_message:
            score += 8

        trigger_hits = sum(1 for trigger in skill.triggers if trigger in lowered_message)
        score += trigger_hits * 3

        description_tokens = set(WORD_PATTERN.findall(skill.description.lower()))
        score += len(message_tokens & description_tokens)

        if score > 0:
            scored.append((score, skill))

    scored.sort(key=lambda item: (-item[0], item[1].name))
    return [skill for _score, skill in scored[:max_matches]]


def render_skill_context(skills: list[SkillDefinition], *, max_chars_per_skill: int = 1200) -> str:
    """Render selected skills into prompt context."""

    if not skills:
        return ""

    lines: list[str] = ["Relevant local skills:"]
    for skill in skills:
        lines.append(f"- name: {skill.name}")
        lines.append(f"  description: {skill.description}")
        lines.append(f"  source: {skill.path}")
        if skill.body:
            clipped = skill.body if len(skill.body) <= max_chars_per_skill else skill.body[:max_chars_per_skill]
            lines.append("  content:")
            for body_line in clipped.splitlines():
                lines.append(f"    {body_line}")
    return "\n".join(lines)


def _normalize_skill_name(name: str) -> str:
    lower = name.strip().lower()
    lower = lower.replace("_", "-").replace(" ", "-")
    lower = SKILL_NAME_PATTERN.sub("-", lower)
    lower = re.sub(r"-{2,}", "-", lower).strip("-")
    return lower or "new-skill"


def _normalize_triggers(
    triggers: tuple[str, ...] | list[str],
    name: str,
    description: str,
) -> tuple[str, ...]:
    tokens = list(triggers) if triggers else []
    if not tokens:
        tokens.extend(_split_tokens(name))
        tokens.extend(_split_tokens(description))

    cleaned: list[str] = []
    for token in tokens:
        normalized = token.strip().lower()
        normalized = normalized.replace("_", "-").replace(" ", "-")
        normalized = SKILL_NAME_PATTERN.sub("-", normalized).strip("-")
        if TRIGGER_PATTERN.match(normalized) and normalized not in cleaned:
            cleaned.append(normalized)
    return tuple(cleaned[:12]) or ("skill",)


def _split_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    if not markdown.startswith(f"{FRONTMATTER_DELIMITER}\n"):
        return {}, markdown

    lines = markdown.splitlines()
    metadata: dict[str, str] = {}
    body_index = 0
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == FRONTMATTER_DELIMITER:
            body_index = idx + 1
            break
        key, sep, value = line.partition(":")
        if not sep:
            continue
        metadata[key.strip().lower()] = value.strip()
    else:
        return {}, markdown

    body = "\n".join(lines[body_index:])
    return metadata, body


def _is_valid_frontmatter(metadata: dict[str, str]) -> bool:
    if not metadata:
        return False

    if set(metadata) != ALLOWED_FRONTMATTER_KEYS:
        return False

    raw_name = metadata.get("name", "").strip()
    raw_description = metadata.get("description", "").strip()
    raw_triggers = metadata.get("triggers", "").strip()

    if not raw_name or raw_name != _normalize_skill_name(raw_name):
        return False
    if not raw_description:
        return False
    trigger_values = _split_csv(raw_triggers)
    if not trigger_values:
        return False
    normalized = _normalize_triggers(trigger_values, raw_name, raw_description)
    return normalized == tuple(trigger_values)


def _split_csv(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    parts = [part.strip() for part in raw.split(",")]
    return tuple(part for part in parts if part)


def _split_tokens(text: str) -> list[str]:
    return WORD_PATTERN.findall(text.lower())


def _resolve_unique_path(skills_dir: Path, base_name: str) -> Path:
    candidate = skills_dir / f"{base_name}.md"
    if not candidate.exists():
        return candidate

    suffix = 2
    while True:
        candidate = skills_dir / f"{base_name}-{suffix}.md"
        if not candidate.exists():
            return candidate
        suffix += 1


def _default_skill_body() -> str:
    return (
        "# Workflow\n\n"
        "1. Identify the user objective and constraints.\n"
        "2. Execute the smallest safe action that advances the objective.\n"
        "3. Verify output before claiming completion.\n"
    )


def _render_skill_markdown(
    name: str,
    description: str,
    triggers: tuple[str, ...],
    body: str,
) -> str:
    normalized_body = body.strip()
    return (
        f"{FRONTMATTER_DELIMITER}\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"triggers: {','.join(triggers)}\n"
        f"{FRONTMATTER_DELIMITER}\n\n"
        f"{normalized_body}\n"
    )
