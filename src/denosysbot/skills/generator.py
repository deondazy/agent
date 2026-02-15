"""Skill markdown synthesis from crawled documentation pages."""

from dataclasses import dataclass
from typing import Any
import re
import shlex

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
VERSION_SPEC_PATTERN = re.compile(r'([:@=])\s*"?[~^]?\d+(?:\.\d+){0,3}"?')
WHITESPACE_PATTERN = re.compile(r"\s+")
MARKDOWN_LINK_PATTERN = re.compile(r"\[(?P<label>[^\]]+)\]\((?P<url>https?://[^)]+)\)")
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "use",
    "using",
    "with",
    "workflow",
    "workflows",
    "concept",
    "concepts",
}


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
    install_commands, common_commands = _split_command_groups(commands)
    page_map = _collect_page_map(pages)
    page_highlights = _collect_page_highlights(pages)

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
    if install_commands:
        body_lines.append("```bash")
        body_lines.extend(install_commands[:14])
        body_lines.append("```")
    elif commands:
        body_lines.append("```bash")
        body_lines.extend(commands[:10])
        body_lines.append("```")
    else:
        body_lines.append("- Review the official docs for exact install commands.")
    body_lines.append("")

    body_lines.append("## Core Concepts")
    for concept in concepts[:20]:
        body_lines.append(f"- {concept}")
    body_lines.append("")

    if common_commands:
        body_lines.append("## Common Commands")
        body_lines.append("```bash")
        body_lines.extend(common_commands[:22])
        body_lines.append("```")
        body_lines.append("")

    if page_highlights:
        body_lines.append("## Page Highlights")
        body_lines.append("| Page | Highlight |")
        body_lines.append("| --- | --- |")
        for page_title, highlight in page_highlights[:20]:
            safe_title = page_title.replace("|", "\\|")
            safe_highlight = highlight.replace("|", "\\|")
            body_lines.append(f"| {safe_title} | {safe_highlight} |")
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
        headings = getattr(page, "headings", ()) or ()
        for heading in headings:
            line = _normalize_sentence(str(heading))
            if line:
                _append_unique(concepts, line)

        excerpt = str(getattr(page, "excerpt", "")).strip()
        if excerpt:
            sentences = [item.strip() for item in SENTENCE_PATTERN.split(excerpt) if item.strip()]
            for sentence in sentences[:4]:
                cleaned = _normalize_sentence(sentence)
                if cleaned and len(cleaned) >= 16:
                    _append_unique(concepts, cleaned)
    return concepts


def _collect_commands(pages: list[Any]) -> list[str]:
    commands: list[str] = []
    signatures: set[str] = set()

    def _push(candidate: str) -> None:
        compact = WHITESPACE_PATTERN.sub(" ", candidate).strip().strip("`")
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
            if not _is_valid_command(item):
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
            if not COMMAND_PATTERN.match(item):
                continue
            signature = _command_signature(item)
            if signature in signatures:
                continue
            signatures.add(signature)
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


def _split_command_groups(commands: list[str]) -> tuple[list[str], list[str]]:
    install_commands: list[str] = []
    common_commands: list[str] = []
    for command in commands:
        lower = command.lower()
        if (
            " install" in lower
            or lower.startswith("composer require ")
            or lower.startswith("npm install")
            or lower.startswith("pnpm install")
            or lower.startswith("yarn install")
            or " create-project " in lower
        ):
            install_commands.append(command)
            continue
        common_commands.append(command)
    return install_commands, common_commands


def _collect_page_map(pages: list[Any]) -> list[tuple[str, str]]:
    mapped: list[tuple[str, str]] = []
    for page in pages:
        url = str(getattr(page, "url", "")).strip()
        title = str(getattr(page, "title", "")).strip() or url
        if url and (title, url) not in mapped:
            mapped.append((title, url))
    return mapped


def _collect_page_highlights(pages: list[Any]) -> list[tuple[str, str]]:
    highlights: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for page in pages:
        title = str(getattr(page, "title", "")).strip() or str(getattr(page, "url", "")).strip()
        highlight = _extract_page_highlight(page)
        if not title or not highlight:
            continue
        signature = (title.lower(), highlight.lower())
        if signature in seen:
            continue
        seen.add(signature)
        highlights.append((title, highlight))
    return highlights


def _extract_page_highlight(page: Any) -> str:
    markdown = str(getattr(page, "markdown", "")).strip()
    if markdown:
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(("#", "```", "|", ">", "-", "*")):
                continue
            if COMMAND_PATTERN.match(line):
                continue
            line = _normalize_sentence(_strip_markdown_links(line))
            if len(line) < 35:
                continue
            return line
    excerpt = _normalize_sentence(str(getattr(page, "excerpt", "")).strip())
    if len(excerpt) >= 35:
        return excerpt
    return ""


def _derive_triggers(skill_name: str, concepts: list[str]) -> tuple[str, ...]:
    triggers: list[str] = []
    for token in skill_name.split("-"):
        if token and token not in triggers and token not in STOPWORDS:
            triggers.append(token)
    for concept in concepts[:10]:
        for token in re.findall(r"[a-z0-9][a-z0-9-]{1,}", concept.lower()):
            if token in STOPWORDS or len(token) < 2:
                continue
            if token not in triggers:
                triggers.append(token)
            if len(triggers) >= 12:
                return tuple(triggers)
    return tuple(triggers or ["skill"])


def _is_valid_command(command: str) -> bool:
    lower = command.lower().strip()
    if lower.startswith("composer config "):
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        if len(parts) < 4:
            return False
    if lower.startswith("composer require "):
        parts = lower.split()
        if len(parts) < 3:
            return False
        if parts[-1] == "require":
            return False
    return True


def _command_signature(command: str) -> str:
    normalized = WHITESPACE_PATTERN.sub(" ", command.strip().lower())
    normalized = VERSION_SPEC_PATTERN.sub(r"\1<VERSION>", normalized)
    normalized = normalized.replace('"', "")
    return normalized


def _normalize_sentence(value: str) -> str:
    line = WHITESPACE_PATTERN.sub(" ", value).strip().rstrip(".")
    return f"{line}." if line else ""


def _append_unique(collection: list[str], value: str) -> None:
    lowered = value.lower()
    if any(item.lower() == lowered for item in collection):
        return
    collection.append(value)


def _strip_markdown_links(value: str) -> str:
    return MARKDOWN_LINK_PATTERN.sub(lambda match: f"{match.group('label')} ({match.group('url')})", value)
