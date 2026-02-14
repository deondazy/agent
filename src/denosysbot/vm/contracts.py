"""VM worker contracts."""

from dataclasses import dataclass


@dataclass(slots=True)
class WorkerContext:
    run_id: str
    vm_id: str
    workspace_dir: str
    root_user: str = "root"
