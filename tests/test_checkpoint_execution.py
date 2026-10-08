from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.fi.checkpoint_faults.memory import MemoryCheckpointFaultInjector
from src.fi.checkpoint_faults.pc import PcCheckpointFault
from src.fi.checkpoint_faults.register import RegisterCheckpointFaultInjector
from src.fi.execution.checkpoint.workspace import Workspace
from src.fi.execution.checkpoint_execution import CheckpointExecutionBackend
from src.fi.execution.factory import ExecutionBackendFactory
from src.fi.experiments.experiment import Experiment
from src.fi.experiments.result import Result
from src.fi.gdb_faults.memory import MemoryFaultInjector
from src.fi.gdb_faults.pc import PcFaultInjector
from src.fi.gdb_faults.register import RegisterFaultInjector


class CheckpointExecutionBackendTests(unittest.TestCase):
    def test_default_workspace_uses_project_checkpoint_script(self) -> None:
        backend = CheckpointExecutionBackend()
        project_root = Path(__file__).resolve().parents[1]

        self.assertEqual(
            Path(backend.workspace.checkpoint_script),
            project_root / "configs" / "simulators" / "gem5" / "gem5_ckpt.py",
        )
        self.assertEqual(
            backend.workspace.root,
            str(project_root / "artifacts" / "gem5" / "checkpoints"),
        )

    def test_factory_selects_checkpoint_backend_for_gem5(self) -> None:
        from src.fi.simulators.gem5 import Gem5Simulator

        simulator = Gem5Simulator(Mock())

        backend = ExecutionBackendFactory.create("checkpoint", simulator)

        self.assertIsInstance(backend, CheckpointExecutionBackend)

    def test_factory_keeps_gdb_as_a_supported_mode(self) -> None:
        from src.fi.execution.gdb_execution import GdbExecutionBackend
        from src.fi.simulators.renode import RenodeSimulator

        backend = ExecutionBackendFactory.create("gdb", RenodeSimulator(Mock()))

        self.assertIsInstance(backend, GdbExecutionBackend)

    def test_experiment_run_delegates_to_selected_backend(self) -> None:
        backend = Mock()
        backend.execute.return_value = Result.SILENT_DATA_CORRUPTION
        experiment = Experiment(
            simulator=Mock(),
            program=self.program,
            fault_injector=RegisterFaultInjector("x5", 0x11111101),
            execution_backend=backend,
        )

        result = experiment.run()

        self.assertIs(result, Result.SILENT_DATA_CORRUPTION)
        backend.execute.assert_called_once_with(experiment)

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.workspace = Workspace(root=self.temporary_directory.name)
        self.backend = CheckpointExecutionBackend(workspace=self.workspace)
        self.program = SimpleNamespace(
            elf_path=Path(self.temporary_directory.name) / "program.elf",
            fault_injection_point=0x80000008,
            end_point=0x80000010,
        )

    def _experiment(
        self,
        injector: object,
        *,
        step_after_injection: bool = False,
        output_register: str = "x10",
    ) -> SimpleNamespace:
        return SimpleNamespace(
            program=self.program,
            fault_injector=injector,
            injection_address=0x80000008,
            end_address=0x80000010,
            output_register=output_register,
            step_after_injection=step_after_injection,
        )

    def test_register_fault_uses_checkpoint_runner_with_original_stop_pcs(self) -> None:
        experiment = self._experiment(RegisterFaultInjector("x5", 0x11111101))

        with patch(
            "src.fi.execution.checkpoint_execution.CheckpointFI"
        ) as runner_type:
            runner_type.return_value.main.return_value = "No effect"
            result = self.backend.execute(experiment)

        self.assertIs(result, Result.NO_EFFECT)
        runner_type.assert_called_once()
        arguments = runner_type.call_args.kwargs
        self.assertEqual(arguments["elf"], str(self.program.elf_path))
        self.assertEqual(arguments["inject_stop_pc"], 0x80000004)
        self.assertEqual(arguments["end_stop_pc"], 0x8000000C)
        self.assertEqual(arguments["result_reg"], 10)
        injector = arguments["fault_injector"]
        self.assertIsInstance(injector, RegisterCheckpointFaultInjector)
        self.assertEqual(injector.register, 5)
        self.assertEqual(injector.value, 0x11111101)
        self.assertIsNone(arguments["faulty_end_stop_pc"])
        self.assertIs(arguments["workspace"], self.workspace)
        runner_type.return_value.main.assert_called_once_with()

    def test_checkpoint_backend_uses_program_symbols_when_addresses_are_omitted(
        self,
    ) -> None:
        experiment = self._experiment(RegisterFaultInjector("x5", 0x11111101))
        experiment.injection_address = None
        experiment.end_address = None

        with patch(
            "src.fi.execution.checkpoint_execution.CheckpointFI"
        ) as runner_type:
            runner_type.return_value.main.return_value = "No effect"
            self.backend.execute(experiment)

        self.assertEqual(
            runner_type.call_args.kwargs["inject_stop_pc"], 0x80000004
        )
        self.assertEqual(
            runner_type.call_args.kwargs["end_stop_pc"], 0x8000000C
        )

    def test_checkpoint_backend_returns_hang_result(self) -> None:
        experiment = self._experiment(RegisterFaultInjector("x5", 0x11111101))

        with patch(
            "src.fi.execution.checkpoint_execution.CheckpointFI"
        ) as runner_type:
            runner_type.return_value.main.return_value = "Hang/crash"
            result = self.backend.execute(experiment)

        self.assertIs(result, Result.HANG_CRASH)

    def test_memory_fault_maps_address_register_to_checkpoint_strategy(self) -> None:
        experiment = self._experiment(MemoryFaultInjector("x5", 0x11111101))

        with patch(
            "src.fi.execution.checkpoint_execution.CheckpointFI"
        ) as runner_type:
            runner_type.return_value.main.return_value = "No effect"
            self.backend.execute(experiment)

        injector = runner_type.call_args.kwargs["fault_injector"]
        self.assertIsInstance(injector, MemoryCheckpointFaultInjector)
        self.assertEqual(injector.address_register, 5)
        self.assertEqual(injector.value, 0x11111101)

    def test_pc_fault_preserves_faulty_stop_pc_after_single_step(self) -> None:
        experiment = self._experiment(
            PcFaultInjector(0x80000010),
            step_after_injection=True,
            output_register="x5",
        )

        with patch(
            "src.fi.execution.checkpoint_execution.CheckpointFI"
        ) as runner_type:
            runner_type.return_value.main.return_value = "No effect"
            self.backend.execute(experiment)

        injector = runner_type.call_args.kwargs["fault_injector"]
        self.assertIsInstance(injector, PcCheckpointFault)
        self.assertEqual(injector.value, 0x80000010)
        self.assertEqual(
            runner_type.call_args.kwargs["faulty_end_stop_pc"], 0x80000010
        )
        self.assertEqual(runner_type.call_args.kwargs["result_reg"], 5)

    def test_memory_fault_rejects_absolute_address_for_checkpoint_strategy(self) -> None:
        experiment = self._experiment(MemoryFaultInjector(0x80001000, 0x11111101))

        with self.assertRaisesRegex(ValueError, "require an address register"):
            self.backend.execute(experiment)


if __name__ == "__main__":
    unittest.main()
