"""Disposable VM provisioner scaffold."""

from openclaw_agent.vm.contracts import WorkerContext


class VMProvisioner:
    """Creates disposable VM contexts for each run."""

    def provision(self, run_id: str) -> WorkerContext:
        return WorkerContext(
            run_id=run_id,
            vm_id=f"vm-{run_id}",
            workspace_dir=f"/workspaces/{run_id}",
        )

    def teardown(self, context: WorkerContext) -> bool:
        # Placeholder for provider-specific cleanup API calls.
        return bool(context.vm_id)
