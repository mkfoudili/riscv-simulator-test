from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from src.fi.experiments.result import Result
from src.fi.execution.pyrenode.backend import PyRenodeExecutionBackend
from src.fi.pyrenode_faults.register import RegisterFaultInjector


class PyRenodeExecutionBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Mock()
        self.program = SimpleNamespace(
            elf_path=Path("/tmp/program.elf"),
            fault_injection_point=0x80000008,
            end_point=0x80000010,
        )
        self.injector = RegisterFaultInjector("x5", 0x11111101)
        self.experiment = SimpleNamespace(
            program=self.program,
            simulator=SimpleNamespace(
                config=SimpleNamespace(timeout=3.0, platform=None)
            ),
            fault_injector=self.injector,
            injection_address=None,
            end_address=None,
            output_register="x10",
            step_after_injection=False,
        )
        self.backend = PyRenodeExecutionBackend()

    def test_runs_baseline_and_faulty_trials_and_classifies_output(self) -> None:
        self.session.read_register.side_effect = [10, 11]

        with patch(
            "src.fi.execution.pyrenode.backend.PyRenodeSession",
            return_value=self.session,
        ) as session_type:
            result = self.backend.execute(self.experiment)

        session_type.assert_called_once_with(
            self.program.elf_path,
            platform=None,
            timeout=3.0,
        )
        self.assertEqual(
            self.session.add_breakpoint.call_args_list,
            [call(0x80000008), call(0x80000010)],
        )
        self.assertEqual(
            self.session.reset.call_count,
            2,
        )
        self.assertEqual(
            self.session.run_until.call_args_list,
            [
                call(0x80000008),
                call(0x80000010),
                call(0x80000008),
                call(0x80000010),
            ],
        )
        self.session.write_register.assert_called_once_with("x5", 0x11111101)
        self.assertIs(result, Result.SILENT_DATA_CORRUPTION)
        self.session.close.assert_called_once_with()

    def test_equal_trial_outputs_report_no_effect(self) -> None:
        self.session.read_register.side_effect = [10, 10]

        with patch(
            "src.fi.execution.pyrenode.backend.PyRenodeSession",
            return_value=self.session,
        ):
            result = self.backend.execute(self.experiment)

        self.assertIs(result, Result.NO_EFFECT)

    def test_timeout_reports_hang_and_still_closes_session(self) -> None:
        self.session.run_until.side_effect = TimeoutError("hang")

        with patch(
            "src.fi.execution.pyrenode.backend.PyRenodeSession",
            return_value=self.session,
        ):
            result = self.backend.execute(self.experiment)

        self.assertIs(result, Result.HANG_CRASH)
        self.session.close.assert_called_once_with()

    def test_step_after_injection_collects_result_after_single_step(self) -> None:
        self.experiment.step_after_injection = True
        self.session.read_register.return_value = 0x1234

        with patch(
            "src.fi.execution.pyrenode.backend.PyRenodeSession",
            return_value=self.session,
        ):
            self.backend.execute(self.experiment)

        self.session.step_instruction.assert_called_once_with()
        self.assertEqual(
            self.session.run_until.call_args_list,
            [call(0x80000008), call(0x80000010), call(0x80000008)],
        )
        self.assertEqual(self.session.read_register.call_count, 2)

    def test_rejects_non_pyrenode_injector_and_does_not_create_session(self) -> None:
        self.experiment.fault_injector = object()

        with patch(
            "src.fi.execution.pyrenode.backend.PyRenodeSession"
        ) as session_type:
            with self.assertRaisesRegex(TypeError, "PyRenode fault injector"):
                self.backend.execute(self.experiment)

        session_type.assert_not_called()


if __name__ == "__main__":
    unittest.main()
