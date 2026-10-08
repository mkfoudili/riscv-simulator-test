from __future__ import annotations

from typing import TYPE_CHECKING

from .result import Result

if TYPE_CHECKING:
    from ..execution.base import ExecutionBackend
    from ..faults.base import GDBFaultInjector
    from ..pyrenode_faults.base import PyRenodeFaultInjector
    from ..program import TestProgram
    from ..simulators.base import Simulator


class Experiment:
    def __init__(
        self,
        simulator: Simulator,
        program: TestProgram,
        fault_injector: GDBFaultInjector | PyRenodeFaultInjector,
        output_register: str = "x10",
        step_after_injection: bool = False,
        injection_address: int | None = None,
        end_address: int | None = None,
        name: str | None = None,
        execution_backend: ExecutionBackend | None = None,
    ) -> None:
        self.simulator = simulator
        self.program = program
        self.fault_injector = fault_injector
        self.output_register = output_register
        self.step_after_injection = step_after_injection
        self.injection_address = injection_address
        self.end_address = end_address
        self.name = name
        self.execution_backend = execution_backend

    def run(self) -> Result:
        backend = self.execution_backend
        if backend is None:
            from ..execution.factory import ExecutionBackendFactory

            from ..pyrenode_faults.base import PyRenodeFaultInjector

            mode = (
                "pyrenode"
                if isinstance(self.fault_injector, PyRenodeFaultInjector)
                else "gdb"
            )
            backend = ExecutionBackendFactory.create(mode, self.simulator)
        return backend.execute(self)