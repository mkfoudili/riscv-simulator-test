from __future__ import annotations

import io
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, call, patch

from run_experiment import main
from src.fi.config.experiment import load_experiment
from src.fi.experiments.result import Result
from src.fi.execution.pyrenode.backend import PyRenodeExecutionBackend
from src.fi.pyrenode_faults.memory import (
    MemoryFaultInjector as PyRenodeMemoryFaultInjector,
)
from src.fi.pyrenode_faults.pc import PcFaultInjector as PyRenodePcFaultInjector
from src.fi.pyrenode_faults.register import (
    RegisterFaultInjector as PyRenodeRegisterFaultInjector,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RunExperimentCliTests(unittest.TestCase):
    def test_loads_and_runs_configured_experiment(self) -> None:
        config_path = PROJECT_ROOT / "configs/experiments/register.toml"
        experiment = Mock(name="register_fault")
        experiment.name = "register_fault"
        experiment.run.return_value = "No effect"
        output = io.StringIO()

        with (
            patch("run_experiment.load_experiment", return_value=experiment) as load,
            redirect_stdout(output),
        ):
            main([str(config_path)])

        load.assert_called_once_with(config_path)
        experiment.run.assert_called_once_with()
        self.assertRegex(
            output.getvalue(),
            re.compile(
                r"^register_fault: No effect\nExecution time: \d+\.\d{3} seconds\n$"
            ),
        )

    def test_requires_one_config_path(self) -> None:
        with self.assertRaises(SystemExit) as error:
            main([])

        self.assertEqual(error.exception.code, 2)

    def test_runs_each_pyrenode_fault_type_from_toml(self) -> None:
        for fault_type in ("register", "memory", "pc"):
            with self.subTest(fault_type=fault_type):
                config_path = (
                    PROJECT_ROOT
                    / "configs"
                    / "experiments"
                    / "pyrenode"
                    / f"{fault_type}.toml"
                )
                experiment = load_experiment(config_path)
                session = Mock()
                session.read_register.return_value = 0
                output = io.StringIO()

                with (
                    patch(
                        "src.fi.execution.pyrenode.backend.PyRenodeSession",
                        return_value=session,
                    ) as session_type,
                    redirect_stdout(output),
                ):
                    main([str(config_path)])

                session_type.assert_called_once()
                self.assertIsInstance(session_type.call_args.kwargs["platform"], Path)
                self.assertEqual(session.reset.call_count, 2)
                self.assertIsInstance(
                    experiment.execution_backend, PyRenodeExecutionBackend
                )
                expected_injectors = {
                    "register": PyRenodeRegisterFaultInjector,
                    "memory": PyRenodeMemoryFaultInjector,
                    "pc": PyRenodePcFaultInjector,
                }
                self.assertIsInstance(
                    experiment.fault_injector, expected_injectors[fault_type]
                )
                if fault_type == "register":
                    session.write_register.assert_called_once_with(
                        "x5", 0x11111101
                    )
                elif fault_type == "memory":
                    session.read_register.assert_any_call("x5")
                    session.write_memory.assert_called_once_with(0, 0x11111101)
                else:
                    session.set_pc.assert_called_once_with(
                        experiment.fault_injector.value
                    )
                    self.assertEqual(
                        session.run_until.call_args_list,
                        [
                            call(experiment.injection_address),
                            call(experiment.end_address),
                            call(experiment.injection_address),
                            call(experiment.end_address),
                        ],
                    )
                    session.step_instruction.assert_not_called()
                self.assertIn(
                    f"pyrenode_{fault_type}_fault: {Result.NO_EFFECT}\n",
                    output.getvalue(),
                )

    def test_experiment_defaults_to_pyrenode_for_pyrenode_injector(self) -> None:
        config_path = (
            PROJECT_ROOT / "configs" / "experiments" / "pyrenode" / "register.toml"
        )
        experiment = load_experiment(config_path)
        experiment.execution_backend = None
        session = Mock()
        session.read_register.return_value = 0

        with patch(
            "src.fi.execution.pyrenode.backend.PyRenodeSession",
            return_value=session,
        ):
            result = experiment.run()

        self.assertIs(result, Result.NO_EFFECT)
        self.assertEqual(session.reset.call_count, 2)
        session.write_register.assert_called_once_with("x5", 0x11111101)
        session.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
