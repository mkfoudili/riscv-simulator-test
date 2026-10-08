import os
import shutil
import subprocess

from ...checkpoint_faults.base import CheckpointFaultInjector
from .state import CheckpointState
from .workspace import Workspace


class CheckpointFI(CheckpointState):
    """Run golden and faulty trials using a checkpoint fault strategy."""

    def __init__(self, elf, inject_stop_pc, end_stop_pc, result_reg,
                 fault_injector: CheckpointFaultInjector,
                 faulty_end_stop_pc=None, timeout=300, workspace=None):
        self.workspace = workspace or Workspace()
        super().__init__(elf, self.workspace)
        self.inject_stop_pc = inject_stop_pc
        self.end_stop_pc = end_stop_pc
        self.faulty_end_stop_pc = faulty_end_stop_pc or end_stop_pc
        self.result_reg = result_reg
        self.fault_injector = fault_injector
        self.timeout = timeout
        self.base = self.workspace.experiment_path(elf)

    def _gem5(self, outdir, *extra):
        os.makedirs(outdir, exist_ok=True)
        cmd = [
            self.workspace.gem5,
            f"--outdir={outdir}",
            self.workspace.checkpoint_script,
            "--elf",
            self.workspace.elf_path(self.elf),
            *extra,
        ]
        result = subprocess.run(
            cmd, cwd=self.workspace.root, capture_output=True, text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout + result.stderr)

    def make_checkpoint(self):
        checkpoint = os.path.join(self.base, "ckpt")
        self._gem5(
            os.path.join(self.base, "m5out_create"),
            "--stop-pc", hex(self.inject_stop_pc),
            "--save-to", checkpoint,
        )
        return checkpoint

    def run(self, ckpt, inject):
        tag = "faulty" if inject else "golden"
        work = os.path.join(self.base, f"ckpt_{tag}")
        final = os.path.join(self.base, f"final_{tag}")
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(final, ignore_errors=True)
        shutil.copytree(ckpt, work)

        if inject:
            self.fault_injector.inject(self, work)

        stop_pc = self.faulty_end_stop_pc if inject else self.end_stop_pc
        try:
            self._gem5(
                os.path.join(self.base, f"m5out_resume_{tag}"),
                "--stop-pc", hex(stop_pc),
                "--restore-from", work,
                "--save-to", final,
            )
        except subprocess.TimeoutExpired:
            return None
        if not os.path.exists(self._cpt(final)):
            return None
        return self.read_reg(final, self.result_reg)

    def main(self) -> str:
        shutil.rmtree(self.base, ignore_errors=True)
        os.makedirs(self.base, exist_ok=True)
        checkpoint = self.make_checkpoint()
        good = self.run(checkpoint, inject=False)
        bad = self.run(checkpoint, inject=True)
        result = ("No effect" if bad == good else
                  "Hang/crash" if bad is None else "Silent data corruption")
        return result
