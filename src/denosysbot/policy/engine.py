"""Policy checks for command execution decisions."""

from dataclasses import dataclass


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False


class PolicyEngine:
    """Command policy evaluator for execution requests."""

    _blocked_exact = {
        "rm -rf /",
        "shutdown -h now",
        "reboot",
    }

    _blocked_fragments = (
        "mkfs",
        "dd if=/dev/zero",
        ":(){ :|:& };:",
    )

    _approval_prefixes = (
        "sudo ",
        "mount ",
        "umount ",
        "chown -R ",
        "chmod -R 777",
    )

    def evaluate_command(self, command: str, approval_token: str | None = None) -> PolicyDecision:
        normalized = command.strip()

        if normalized in self._blocked_exact:
            return PolicyDecision(allowed=False, reason="blocked_by_policy")

        if any(fragment in normalized for fragment in self._blocked_fragments):
            return PolicyDecision(allowed=False, reason="blocked_by_policy")

        needs_approval = normalized.startswith(self._approval_prefixes)
        if needs_approval and not approval_token:
            return PolicyDecision(
                allowed=False,
                reason="approval_required",
                requires_approval=True,
            )

        return PolicyDecision(allowed=True, reason="allowed")
