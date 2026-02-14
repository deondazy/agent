"""GitHub repository adapter scaffold."""

from dataclasses import dataclass


@dataclass(slots=True)
class GitHubRepoTarget:
    owner: str
    name: str
    default_branch: str = "main"


class GitHubRepoAdapter:
    """Thin contract for GitHub operations."""

    def issue_ref(self, target: GitHubRepoTarget, issue_number: int) -> str:
        return f"{target.owner}/{target.name}#{issue_number}"

    def pr_title(self, issue_title: str) -> str:
        return f"fix: {issue_title}".strip()
