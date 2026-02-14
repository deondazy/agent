"""Local repository adapter scaffold."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class LocalRepoTarget:
    path: Path
    default_branch: str = "main"


class LocalRepoAdapter:
    """Thin contract for local repository operations."""

    def checkout(self, target: LocalRepoTarget) -> Path:
        return target.path

    def create_branch_name(self, run_id: str, slug: str = "issue") -> str:
        return f"codex/{run_id}-{slug}"
