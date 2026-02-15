"""Skill markdown synthesis from crawled documentation pages."""

from dataclasses import dataclass
from typing import Any
import re

COMMAND_PATTERN = re.compile(
    (
        r"^\s*(?:"
        r"composer\s+(?:require|config|install|update|remove|dump-autoload|create-project)\b|"
        r"php artisan\s+[a-z0-9:-]+|"
        r"npm\s+(?:install|run|ci|build|dev|test)\b|"
        r"pnpm\s+(?:install|run|build|dev|test)\b|"
        r"yarn\s+(?:install|add|run|build|dev|test)\b|"
        r"pip\s+install\b|"
        r"poetry\s+(?:add|install|run)\b|"
        r"uv\s+(?:pip|run|add|sync)\b|"
        r"docker\s+[a-z0-9-]+"
        r")\b.*$"
    ),
    flags=re.IGNORECASE,
)
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class SkillDraft:
    name: str
    description: str
    triggers: tuple[str, ...]
    body: str

    def to_markdown(self) -> str:
        return (
            "---\n"
            f"name: {self.name}\n"
            f"description: {self.description}\n"
            f"triggers: {','.join(self.triggers)}\n"
            "---\n\n"
            f"{self.body.strip()}\n"
        )


def build_skill_draft(
    *,
    skill_name: str,
    source_url: str,
    pages: list[Any],
) -> SkillDraft:
    """Build a structured skill draft from crawled docs pages."""

    normalized_name = _normalize_name(skill_name)
    display_name = _display_name(normalized_name)
    documentation_urls = _collect_urls(source_url, pages)
    concepts = _collect_concepts(pages)
    commands = _collect_commands(pages)
    page_map = _collect_page_map(pages)

    if not concepts:
        concepts = ["Use crawled documentation pages as authoritative guidance."]

    body_lines = [
        f"# {display_name}",
        "",
        "Learned from crawled official documentation pages.",
        "",
        "## Documentation",
    ]
    body_lines.extend([f"- {url}" for url in documentation_urls])
    body_lines.append("")

    body_lines.append("## Installation & Setup")
    if commands:
        body_lines.append("```bash")
        body_lines.extend(commands[:12])
        body_lines.append("```")
    else:
        body_lines.append("- Review the official docs for exact install commands.")
    body_lines.append("")

    body_lines.append("## Core Concepts")
    for concept in concepts[:20]:
        body_lines.append(f"- {concept}")
    body_lines.append("")

    if commands:
        body_lines.append("## Common Commands")
        body_lines.append("```bash")
        body_lines.extend(commands[:20])
        body_lines.append("```")
        body_lines.append("")

    if page_map:
        body_lines.append("## Page Map")
        body_lines.append("| Page | URL |")
        body_lines.append("| --- | --- |")
        for title, url in page_map[:25]:
            safe_title = title.replace("|", "\\|")
            safe_url = url.replace("|", "%7C")
            body_lines.append(f"| {safe_title} | {safe_url} |")
        body_lines.append("")

    body_lines.append("## Usage Guidance")
    body_lines.append("1. Use these documented APIs and commands first.")
    body_lines.append("2. Prefer version-specific pages for the requested version.")
    body_lines.append("3. If behavior is unclear, cite and compare multiple docs pages.")

    description = (
        f"How to use {display_name} based on crawled documentation pages. "
        f"Use when users ask about {display_name} implementation details, setup, commands, or best practices."
    )
    triggers = _derive_triggers(normalized_name, concepts)
    return SkillDraft(
        name=normalized_name,
        description=description,
        triggers=triggers,
        body="\n".join(body_lines),
    )


def build_skill_markdown(
    *,
    skill_name: str,
    source_url: str,
    pages: list[Any],
) -> str:
    """Build full SKILL.md markdown including frontmatter."""

    return build_skill_draft(skill_name=skill_name, source_url=source_url, pages=pages).to_markdown()


def _normalize_name(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "learned-skill"


def _display_name(skill_name: str) -> str:
    if skill_name == "filament-v5":
        return "FilamentPHP v5"
    return skill_name.replace("-", " ").title()


def _collect_urls(source_url: str, pages: list[Any]) -> list[str]:
    urls: list[str] = [source_url]
    for page in pages:
        url = str(getattr(page, "url", "")).strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def _collect_concepts(pages: list[Any]) -> list[str]:
    concepts: list[str] = []
    for page in pages:
        title = str(getattr(page, "title", "")).strip()
        if title:
            candidate = f"{title} concepts and workflows."
            if candidate not in concepts:
                concepts.append(candidate)

        headings = getattr(page, "headings", ()) or ()
        for heading in headings:
            line = str(heading).strip()
            if line:
                candidate = f"{line}."
                if candidate not in concepts:
                    concepts.append(candidate)

        excerpt = str(getattr(page, "excerpt", "")).strip()
        if excerpt:
            sentences = [item.strip() for item in SENTENCE_PATTERN.split(excerpt) if item.strip()]
            for sentence in sentences[:3]:
                cleaned = sentence.rstrip(".")
                if len(cleaned) >= 12 and cleaned not in concepts:
                    concepts.append(cleaned)
    return concepts


def _collect_commands(pages: list[Any]) -> list[str]:
    commands: list[str] = []

    def _push(candidate: str) -> None:
        compact = re.sub(r"\s+", " ", candidate).strip().strip("`")
        if not compact:
            return

        segments = re.split(
            r"(?=(?:composer|php artisan|npm|pnpm|yarn|pip|poetry|uv|docker)\b)",
            compact,
            flags=re.IGNORECASE,
        )
        for segment in segments:
            item = segment.strip(" ;")
            if not item:
                continue
            if len(item) > 220:
                continue
            lower = item.lower()
            if lower in {
                "composer require",
                "composer config",
                "npm run",
                "yarn run",
                "pnpm run",
                "php artisan",
            }:
                continue
            if COMMAND_PATTERN.match(item) and item not in commands:
                commands.append(item)

    for page in pages:
        blocks = getattr(page, "code_blocks", ()) or ()
        for block in blocks:
            for line in str(block).splitlines():
                _push(line)

        markdown = str(getattr(page, "markdown", "")).strip()
        if markdown:
            for line in markdown.splitlines():
                _push(line)
    return commands


def _collect_page_map(pages: list[Any]) -> list[tuple[str, str]]:
    mapped: list[tuple[str, str]] = []
    for page in pages:
        url = str(getattr(page, "url", "")).strip()
        title = str(getattr(page, "title", "")).strip() or url
        if url and (title, url) not in mapped:
            mapped.append((title, url))
    return mapped


def _derive_triggers(skill_name: str, concepts: list[str]) -> tuple[str, ...]:
    triggers: list[str] = []
    for token in skill_name.split("-"):
        if token and token not in triggers:
            triggers.append(token)
    for concept in concepts[:10]:
        for token in re.findall(r"[a-z0-9][a-z0-9-]{1,}", concept.lower()):
            if token not in triggers:
                triggers.append(token)
            if len(triggers) >= 12:
                return tuple(triggers)
    return tuple(triggers or ["skill"])
