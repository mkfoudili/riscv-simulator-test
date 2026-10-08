from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..checkpoint_faults.base import CheckpointFaultInjector
from ..checkpoint_faults.memory import MemoryCheckpointFaultInjector
from ..checkpoint_faults.pc import PcCheckpointFault
from ..checkpoint_faults.register import RegisterCheckpointFaultInjector
from ..gdb_faults.memory import MemoryFaultInjector
from ..gdb_faults.pc import PcFaultInjector
from ..gdb_faults.register import RegisterFaultInjector
from .base import ExecutionBackend
from .checkpoint.runner import CheckpointFI
from .checkpoint.workspace import Workspace
from ..experiments.result import Result

if TYPE_CHECKING:
    from ..experiments.experiment import Experiment


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class CheckpointExecutionBackend(ExecutionBackend):
    def __init__(self, workspace: Workspace | None = None) -> None:
        self.workspace = workspace or Workspace(
            root=PROJECT_ROOT / "artifacts" / "gem5" / "checkpoints",
            checkpoint_script=(
                PROJECT_ROOT / "configs" / "simulators" / "gem5" / "gem5_ckpt.py"
            ),
        )

    def execute(self, experiment: Experiment) -> Result:
        fault_injector = self._checkpoint_fault(experiment.fault_injector)
        injection_address = (
            experiment.injection_address
            if experiment.injection_address is not None
            else experiment.program.fault_injection_point
        )
        end_address = (
            experiment.end_address
            if experiment.end_address is not None
            else experiment.program.end_point
        )
        faulty_end_stop_pc = (
            fault_injector.value
            if experiment.step_after_injection
            and isinstance(fault_injector, PcCheckpointFault)
            else None
        )
        runner = CheckpointFI(
            elf=str(experiment.program.elf_path),
            inject_stop_pc=injection_address - 4,
            end_stop_pc=end_address - 4,
            result_reg=self._register_number(experiment.output_register),
            fault_injector=fault_injector,
            faulty_end_stop_pc=faulty_end_stop_pc,
            workspace=self.workspace,
        )
        result = runner.main()
        if result == "No effect":
            return Result.NO_EFFECT
        if result == "Hang/crash":
            return Result.HANG_CRASH
        if result == "Silent data corruption":
            return Result.SILENT_DATA_CORRUPTION
        raise RuntimeError(f"unexpected checkpoint result: {result!r}")

    @classmethod
    def _checkpoint_fault(
        cls,
        fault_injector: object,
    ) -> CheckpointFaultInjector:
        if isinstance(fault_injector, CheckpointFaultInjector):
            return fault_injector
        if isinstance(fault_injector, RegisterFaultInjector):
            return RegisterCheckpointFaultInjector(
                register=cls._register_number(fault_injector.register),
                value=fault_injector.value,
            )
        if isinstance(fault_injector, MemoryFaultInjector):
            if not isinstance(fault_injector.address, str):
                raise ValueError(
                    "checkpoint memory faults require an address register"
                )
            return MemoryCheckpointFaultInjector(
                address_register=cls._register_number(fault_injector.address),
                value=fault_injector.value,
            )
        if isinstance(fault_injector, PcFaultInjector):
            return PcCheckpointFault(value=fault_injector.value)
        raise TypeError(
            f"unsupported checkpoint fault injector: "
            f"{type(fault_injector).__name__}"
        )

    @staticmethod
    def _register_number(register: str) -> int:
        if not register.startswith("x") or not register[1:].isdigit():
            raise ValueError(
                f"checkpoint faults require an integer RISC-V register, "
                f"got {register!r}"
            )
        number = int(register[1:])
        if not 0 <= number < 32:
            raise ValueError(f"RISC-V register is out of range: {register!r}")
        return number