"""Skill markdown synthesis from crawled documentation pages."""

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any
import json
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
NON_ALPHA_PATTERN = re.compile(r"[^a-z0-9-]+")
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
    model_generate: Callable[[str], str] | None = None,
) -> SkillDraft:
    """Build a structured skill draft from crawled docs pages."""

    normalized_name = _normalize_name(skill_name)
    display_name = _display_name(normalized_name)
    documentation_urls = _collect_urls(source_url, pages)
    page_map = _collect_page_map(pages)

    if model_generate and _can_use_model_synthesis(pages):
        drafted = _build_model_assisted_draft(
            normalized_name=normalized_name,
            display_name=display_name,
            source_url=source_url,
            documentation_urls=documentation_urls,
            page_map=page_map,
            pages=pages,
            model_generate=model_generate,
        )
        if drafted is not None:
            return drafted

    return _build_heuristic_skill_draft(
        normalized_name=normalized_name,
        display_name=display_name,
        source_url=source_url,
        documentation_urls=documentation_urls,
        page_map=page_map,
        pages=pages,
    )


def build_skill_markdown(
    *,
    skill_name: str,
    source_url: str,
    pages: list[Any],
    model_generate: Callable[[str], str] | None = None,
) -> str:
    """Build full SKILL.md markdown including frontmatter."""

    return build_skill_draft(
        skill_name=skill_name,
        source_url=source_url,
        pages=pages,
        model_generate=model_generate,
    ).to_markdown()


def _build_heuristic_skill_draft(
    *,
    normalized_name: str,
    display_name: str,
    source_url: str,
    documentation_urls: list[str],
    page_map: list[tuple[str, str]],
    pages: list[Any],
) -> SkillDraft:
    concepts = _collect_concepts(pages)
    commands = _collect_commands(pages)
    install_commands, common_commands = _split_command_groups(commands)
    page_highlights = _collect_page_highlights(pages)

    if not concepts:
        concepts = ["Use crawled documentation pages as authoritative guidance."]

    body_lines = _render_skill_body(
        display_name=display_name,
        source_url=source_url,
        documentation_urls=documentation_urls,
        page_map=page_map,
        concepts=concepts,
        install_commands=install_commands,
        common_commands=common_commands,
        page_highlights=page_highlights,
        best_practices=(),
        pitfalls=(),
        include_learned_intro=True,
    )

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


def _can_use_model_synthesis(pages: list[Any]) -> bool:
    for page in pages:
        markdown = str(getattr(page, "markdown", "")).strip()
        headings = tuple(getattr(page, "headings", ()) or ())
        blocks = tuple(getattr(page, "code_blocks", ()) or ())
        if len(markdown) >= 160 or len(headings) >= 3 or len(blocks) >= 2:
            return True
    return False


def _build_model_assisted_draft(
    *,
    normalized_name: str,
    display_name: str,
    source_url: str,
    documentation_urls: list[str],
    page_map: list[tuple[str, str]],
    pages: list[Any],
    model_generate: Callable[[str], str],
) -> SkillDraft | None:
    prompt = _build_model_prompt(
        display_name=display_name,
        source_url=source_url,
        pages=pages,
    )
    try:
        raw = model_generate(prompt)
    except Exception:
        return None

    payload = _parse_model_payload(raw)
    if payload is None:
        return None

    concepts = _coerce_string_list(payload.get("core_concepts"), max_items=24, min_len=8)
    if not concepts:
        concepts = _collect_concepts(pages)
    if not concepts:
        concepts = ["Use crawled documentation pages as authoritative guidance."]

    commands = _collect_commands(pages)
    install_commands, common_commands = _split_command_groups(commands)
    model_install = _coerce_commands(payload.get("installation_commands"), max_items=20)
    model_common = _coerce_commands(payload.get("common_commands"), max_items=26)
    if model_install:
        install_commands = _merge_commands(model_install, install_commands, max_items=20)
    if model_common:
        common_commands = _merge_commands(model_common, common_commands, max_items=26)
    if not common_commands:
        common_commands = [item for item in commands if item not in install_commands][:26]

    page_highlights = _coerce_page_highlights(payload.get("page_highlights"), fallback_pages=pages)
    if not page_highlights:
        page_highlights = _collect_page_highlights(pages)

    best_practices = _coerce_string_list(payload.get("best_practices"), max_items=12, min_len=14)
    pitfalls = _coerce_string_list(payload.get("pitfalls"), max_items=10, min_len=14)

    body_lines = _render_skill_body(
        display_name=display_name,
        source_url=source_url,
        documentation_urls=documentation_urls,
        page_map=page_map,
        concepts=concepts,
        install_commands=install_commands,
        common_commands=common_commands,
        page_highlights=page_highlights,
        best_practices=best_practices,
        pitfalls=pitfalls,
        include_learned_intro=True,
    )

    raw_description = str(payload.get("description", "")).strip()
    if len(raw_description) < 30:
        description = (
            f"How to use {display_name} based on crawled documentation pages. "
            f"Use when users ask about {display_name} implementation details, setup, commands, or best practices."
        )
    else:
        description = WHITESPACE_PATTERN.sub(" ", raw_description)[:320]

    candidate_triggers = _coerce_string_list(payload.get("triggers"), max_items=12, min_len=2)
    trigger_tokens = _normalize_trigger_tokens(candidate_triggers)
    if not trigger_tokens:
        trigger_tokens = _derive_triggers(normalized_name, concepts)

    return SkillDraft(
        name=normalized_name,
        description=description,
        triggers=trigger_tokens,
        body="\n".join(body_lines),
    )


def _build_model_prompt(
    *,
    display_name: str,
    source_url: str,
    pages: list[Any],
) -> str:
    corpus = _build_model_corpus(pages)
    return (
        "You are generating a SKILL.md synthesis from crawled documentation pages.\n"
        "Use only facts from the provided corpus. Do not invent APIs, commands, or behavior.\n"
        "Return strict JSON with this exact shape:\n"
        "{\n"
        '  "description": "string",\n'
        '  "triggers": ["string"],\n'
        '  "core_concepts": ["string"],\n'
        '  "installation_commands": ["command"],\n'
        '  "common_commands": ["command"],\n'
        '  "best_practices": ["string"],\n'
        '  "pitfalls": ["string"],\n'
        '  "page_highlights": [{"page": "string", "url": "https://...", "highlight": "string"}]\n'
        "}\n"
        "Constraints:\n"
        "- Keep concepts actionable and specific to the docs.\n"
        "- Include installation commands only if directly evidenced.\n"
        "- Keep command entries as runnable shell lines (no prose).\n"
        "- For page_highlights, prefer 1 sentence grounded in that page content.\n"
        f"- Topic: {display_name}\n"
        f"- Source URL: {source_url}\n"
        "\n"
        "Corpus:\n"
        f"{corpus}\n"
    )


def _build_model_corpus(pages: list[Any]) -> str:
    lines: list[str] = []
    for index, page in enumerate(pages[:36], start=1):
        url = str(getattr(page, "url", "")).strip()
        title = str(getattr(page, "title", "")).strip() or url
        excerpt = WHITESPACE_PATTERN.sub(" ", str(getattr(page, "excerpt", "")).strip())
        headings = [str(item).strip() for item in (getattr(page, "headings", ()) or ()) if str(item).strip()]
        commands = _collect_commands([page])[:8]
        facts = _extract_fact_lines(page)[:6]

        lines.append(f"Page {index}: {title}")
        lines.append(f"URL: {url}")
        if headings:
            lines.append(f"Headings: {', '.join(headings[:8])}")
        if excerpt:
            lines.append(f"Excerpt: {excerpt[:360]}")
        if commands:
            lines.append("Commands:")
            for command in commands:
                lines.append(f"- {command}")
        if facts:
            lines.append("Key facts:")
            for fact in facts:
                lines.append(f"- {fact}")
        lines.append("")
    return "\n".join(lines).strip()


def _extract_fact_lines(page: Any) -> list[str]:
    facts: list[str] = []
    markdown = str(getattr(page, "markdown", "")).strip()
    if markdown:
        for raw_line in markdown.splitlines():
            line = WHITESPACE_PATTERN.sub(" ", raw_line).strip()
            if not line:
                continue
            if line.startswith(("#", "```", "|", ">", "-", "*")):
                continue
            if COMMAND_PATTERN.match(line):
                continue
            line = _strip_markdown_links(line)
            if len(line) < 35 or len(line) > 300:
                continue
            if line not in facts:
                facts.append(line)
            if len(facts) >= 8:
                break
    if not facts:
        excerpt = str(getattr(page, "excerpt", "")).strip()
        if excerpt:
            facts.append(WHITESPACE_PATTERN.sub(" ", excerpt)[:300])
    return facts


def _parse_model_payload(raw: str) -> dict[str, Any] | None:
    candidate = raw.strip()
    if not candidate:
        return None
    if "```" in candidate:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, flags=re.DOTALL)
        if match:
            candidate = match.group(1).strip()
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _coerce_string_list(value: Any, *, max_items: int, min_len: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = WHITESPACE_PATTERN.sub(" ", str(raw)).strip()
        if len(text) < min_len:
            continue
        if text.endswith(":"):
            continue
        if text not in items:
            items.append(text)
        if len(items) >= max_items:
            break
    return items


def _coerce_commands(value: Any, *, max_items: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    signatures: set[str] = set()
    for raw in value:
        command = WHITESPACE_PATTERN.sub(" ", str(raw)).strip().strip("`")
        if not command:
            continue
        if not _is_valid_command(command):
            continue
        if not COMMAND_PATTERN.match(command):
            continue
        signature = _command_signature(command)
        if signature in signatures:
            continue
        signatures.add(signature)
        items.append(command)
        if len(items) >= max_items:
            break
    return items


def _merge_commands(primary: list[str], secondary: list[str], *, max_items: int) -> list[str]:
    merged: list[str] = []
    signatures: set[str] = set()
    for command in [*primary, *secondary]:
        signature = _command_signature(command)
        if signature in signatures:
            continue
        signatures.add(signature)
        merged.append(command)
        if len(merged) >= max_items:
            break
    return merged


def _coerce_page_highlights(value: Any, *, fallback_pages: list[Any]) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        return []

    known_pages: dict[str, str] = {}
    for page in fallback_pages:
        url = str(getattr(page, "url", "")).strip()
        title = str(getattr(page, "title", "")).strip() or url
        if url and url not in known_pages:
            known_pages[url] = title

    highlights: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in value:
        if not isinstance(raw, dict):
            continue
        url = WHITESPACE_PATTERN.sub(" ", str(raw.get("url", ""))).strip()
        if not url:
            continue
        if url not in known_pages:
            continue
        page_name = WHITESPACE_PATTERN.sub(" ", str(raw.get("page", ""))).strip() or known_pages[url]
        highlight = WHITESPACE_PATTERN.sub(" ", str(raw.get("highlight", ""))).strip()
        if len(highlight) < 24:
            continue
        signature = (page_name.lower(), highlight.lower())
        if signature in seen:
            continue
        seen.add(signature)
        highlights.append((page_name, highlight))
        if len(highlights) >= 22:
            break
    return highlights


def _normalize_trigger_tokens(tokens: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for token in tokens:
        value = token.strip().lower()
        value = NON_ALPHA_PATTERN.sub("-", value).strip("-")
        if len(value) < 2:
            continue
        if value in STOPWORDS:
            continue
        if value not in normalized:
            normalized.append(value)
        if len(normalized) >= 12:
            break
    return tuple(normalized)


def _render_skill_body(
    *,
    display_name: str,
    source_url: str,
    documentation_urls: list[str],
    page_map: list[tuple[str, str]],
    concepts: list[str],
    install_commands: list[str],
    common_commands: list[str],
    page_highlights: list[tuple[str, str]],
    best_practices: tuple[str, ...] | list[str],
    pitfalls: tuple[str, ...] | list[str],
    include_learned_intro: bool,
) -> list[str]:
    body_lines = [f"# {display_name}", ""]
    if include_learned_intro:
        body_lines.append("Learned from crawled official documentation pages.")
        body_lines.append("")

    body_lines.append("## Documentation")
    body_lines.extend([f"- {url}" for url in documentation_urls])
    body_lines.append("")

    body_lines.append("## Installation & Setup")
    if install_commands:
        body_lines.append("```bash")
        body_lines.extend(install_commands[:14])
        body_lines.append("```")
    else:
        body_lines.append("- Review the official docs for exact install commands.")
    body_lines.append("")

    body_lines.append("## Core Concepts")
    for concept in concepts[:22]:
        body_lines.append(f"- {concept}")
    body_lines.append("")

    if common_commands:
        body_lines.append("## Common Commands")
        body_lines.append("```bash")
        body_lines.extend(common_commands[:24])
        body_lines.append("```")
        body_lines.append("")

    if best_practices:
        body_lines.append("## Best Practices")
        for item in best_practices[:12]:
            body_lines.append(f"- {item}")
        body_lines.append("")

    if pitfalls:
        body_lines.append("## Pitfalls & Notes")
        for item in pitfalls[:10]:
            body_lines.append(f"- {item}")
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
        for title, url in page_map[:35]:
            safe_title = title.replace("|", "\\|")
            safe_url = url.replace("|", "%7C")
            body_lines.append(f"| {safe_title} | {safe_url} |")
        body_lines.append("")

    body_lines.append("## Usage Guidance")
    body_lines.append("1. Use these documented APIs and commands first.")
    body_lines.append("2. Prefer version-specific pages for the requested version.")
    body_lines.append("3. If behavior is unclear, cite and compare multiple docs pages.")
    body_lines.append(f"4. Start from {source_url} when onboarding new tasks.")
    return body_lines


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
