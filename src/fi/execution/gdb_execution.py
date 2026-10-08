from __future__ import annotations

from typing import TYPE_CHECKING

from ..experiments.result import Result, ResultClassifier
from .base import ExecutionBackend

if TYPE_CHECKING:
    from ..experiments.experiment import Experiment
    from ..simulators.base import Simulator


class GdbExecutionBackend(ExecutionBackend):
    def execute(self, experiment: Experiment) -> Result:
        correct_output = self._run_trial(experiment, inject_fault=False)
        faulty_output = self._run_trial(experiment, inject_fault=True)
        return ResultClassifier.classify(correct_output, faulty_output)

    @staticmethod
    def _run_trial(experiment: Experiment, inject_fault: bool) -> int:
        trial = _GdbExperimentTrial(experiment, inject_fault)
        return experiment.simulator.run(experiment.program.elf_path, trial)


class _GdbExperimentTrial:
    def __init__(self, experiment: Experiment, inject_fault: bool) -> None:
        self.experiment = experiment
        self.inject_fault = inject_fault

    def execute(self, simulator: Simulator) -> int:
        from ..gdb.client import GdbClient

        gdb = GdbClient(simulator.config)
        try:
            gdb.start(self.experiment.program.elf_path)
            endpoint = simulator.gdb_endpoint
            gdb.connect(endpoint.host, endpoint.port)
            injection_address = self.experiment.injection_address
            if injection_address is None:
                injection_address = self.experiment.program.fault_injection_point
            end_address = self.experiment.end_address
            if end_address is None:
                end_address = self.experiment.program.end_point
            gdb.set_breakpoint(injection_address)
            gdb.set_breakpoint(end_address)

            gdb.continue_execution()
            if self.inject_fault:
                self.experiment.fault_injector.inject(gdb)
                if self.experiment.step_after_injection:
                    gdb.step_instruction()
                else:
                    gdb.continue_execution()
            else:
                gdb.continue_execution()
            return gdb.read_register(self.experiment.output_register)
        finally:
            gdb.close()