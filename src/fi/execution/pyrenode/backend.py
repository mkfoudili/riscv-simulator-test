from __future__ import annotations

from typing import TYPE_CHECKING

from ...experiments.result import Result, ResultClassifier
from ...pyrenode_faults.base import PyRenodeFaultInjector
from .session import PyRenodeSession
from ..base import ExecutionBackend

if TYPE_CHECKING:
    from ...experiments.experiment import Experiment


class PyRenodeExecutionBackend(ExecutionBackend):
    def execute(self, experiment: Experiment) -> Result:
        if not isinstance(experiment.fault_injector, PyRenodeFaultInjector):
            raise TypeError(
                "PyRenode execution requires a PyRenode fault injector, got "
                f"{type(experiment.fault_injector).__name__}"
            )

        session = PyRenodeSession(
            experiment.program.elf_path,
            platform=experiment.simulator.config.platform,
            timeout=experiment.simulator.config.timeout,
        )
        try:
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
            session.add_breakpoint(injection_address)
            session.add_breakpoint(end_address)

            correct_output = self._run_trial(
                experiment,
                session,
                injection_address,
                end_address,
                inject_fault=False,
            )
            faulty_output = self._run_trial(
                experiment,
                session,
                injection_address,
                end_address,
                inject_fault=True,
            )
        except TimeoutError:
            return Result.HANG_CRASH
        else:
            return ResultClassifier.classify(correct_output, faulty_output)
        finally:
            session.close()

    @staticmethod
    def _run_trial(
        experiment: Experiment,
        session: PyRenodeSession,
        injection_address: int,
        end_address: int,
        *,
        inject_fault: bool,
    ) -> int:
        session.reset()
        session.run_until(injection_address)
        if inject_fault:
            experiment.fault_injector.inject(session)
            if experiment.step_after_injection:
                session.step_instruction()
                return session.read_register(experiment.output_register)
        session.run_until(end_address)
        return session.read_register(experiment.output_register)