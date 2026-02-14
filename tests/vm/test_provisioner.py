from denosysbot.vm.provisioner import VMProvisioner


def test_provisioner_returns_worker_context() -> None:
    context = VMProvisioner().provision("run-1")

    assert context.run_id == "run-1"
    assert context.vm_id == "vm-run-1"
