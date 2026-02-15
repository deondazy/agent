# DenosysBot Web + Skills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real internet browsing support, Markdown skill creation/learning, and automatic skill usage in DenosysBot chat.

**Architecture:** Introduce two small modules: a `skills` engine for Markdown skill discovery/matching and a `tools.web` helper for internet lookup. Wire both into `run_tui` so commands can create/list/learn skills and regular prompts can include relevant skill/web context.

**Tech Stack:** Python 3.12, `httpx`, existing DenosysBot CLI + pytest.

### Task 1: Tests for Skills Engine + CLI Commands

**Files:**
- Create: `tests/test_skills_engine.py`
- Modify: `tests/test_cli.py`

1. Add failing tests for skill file creation and frontmatter parsing.
2. Add failing tests for matching relevant skills from user text.
3. Add failing test for `/skill create` command writing `.md` file.
4. Run target tests to confirm failures.

### Task 2: Implement Skills Engine

**Files:**
- Create: `src/denosysbot/skills/__init__.py`
- Create: `src/denosysbot/skills/engine.py`

1. Add `SkillDefinition` and frontmatter parsing.
2. Add skill loading from a configurable directory.
3. Add relevance matching and prompt context rendering.
4. Add markdown skill creation utility.

### Task 3: Implement Web Browsing Helper

**Files:**
- Create: `src/denosysbot/tools/__init__.py`
- Create: `src/denosysbot/tools/web.py`
- Create: `tests/test_web_tools.py`

1. Add web search using live HTTP requests.
2. Add URL normalization for DuckDuckGo redirect links.
3. Add optional page-text extraction and compact context rendering.
4. Add tests for parsing and normalization behavior.

### Task 4: Wire into CLI

**Files:**
- Modify: `src/denosysbot/cli.py`
- Modify: `tests/test_cli.py`

1. Add skill path resolution and command handlers:
   - `/skills`
   - `/skill create <name> | <description> | <triggers>`
   - `/skill learn <name> | <topic>`
2. Add `/web <query>` command for direct browsing results.
3. Auto-load relevant skills for normal messages and append to prompt.
4. Add optional auto-web research hook for time-sensitive/search prompts.
5. Ensure failures degrade gracefully (no crash, explanatory output).

### Task 5: Verification

**Files:**
- N/A (commands only)

1. Run focused tests for new modules and CLI behavior.
2. Run broader suite (`pytest -q`) as final confidence check.
3. Summarize capabilities, exact commands, and known limits.
