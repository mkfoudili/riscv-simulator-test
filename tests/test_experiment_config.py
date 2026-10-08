from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from src.fi.config.experiment import load_experiment
from src.fi.execution.checkpoint_execution import CheckpointExecutionBackend
from src.fi.execution.gdb_execution import GdbExecutionBackend
from src.fi.execution.pyrenode.backend import PyRenodeExecutionBackend
from src.fi.faults.memory import MemoryFaultInjector
from src.fi.faults.pc import PcFaultInjector
from src.fi.faults.register import RegisterFaultInjector
from src.fi.pyrenode_faults.register import (
    RegisterFaultInjector as PyRenodeRegisterFaultInjector,
)
from src.fi.pyrenode_faults.memory import (
    MemoryFaultInjector as PyRenodeMemoryFaultInjector,
)
from src.fi.pyrenode_faults.pc import PcFaultInjector as PyRenodePcFaultInjector
from src.fi.simulators.gem5 import Gem5Simulator
from src.fi.simulators.qemu import QemuSimulator
from src.fi.simulators.renode import RenodeSimulator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = PROJECT_ROOT / "configs" / "experiments"


class ExperimentConfigTests(unittest.TestCase):
    def test_register_toml_builds_experiment_objects(self) -> None:
        experiment = load_experiment(EXPERIMENTS_DIR / "register.toml")

        self.assertEqual(experiment.name, "register_fault")
        self.assertEqual(experiment.program.source, "register_test.S")
        self.assertEqual(experiment.program.elf, "register_test.elf")
        self.assertIsInstance(experiment.simulator, Gem5Simulator)
        self.assertEqual(experiment.injection_address, 0x80000008)
        self.assertEqual(experiment.end_address, 0x8000000C)
        self.assertEqual(experiment.output_register, "x10")
        self.assertFalse(experiment.step_after_injection)
        self.assertIsInstance(experiment.fault_injector, RegisterFaultInjector)
        self.assertEqual(experiment.fault_injector.register, "x5")
        self.assertEqual(experiment.fault_injector.value, 0x11111101)
        self.assertIsInstance(experiment.execution_backend, GdbExecutionBackend)

    def test_checkpoint_execution_backend_can_be_selected_in_config(self) -> None:
        source = (EXPERIMENTS_DIR / "register.toml").read_text()
        source = source.replace(
            'name = "renode"',
            'name = "gem5"',
            1,
        ).replace(
            "[execution]",
            '[execution]\nmode = "checkpoint"',
        )

        with TemporaryDirectory(prefix="checkpoint-experiment-") as directory:
            config_path = Path(directory) / "experiment.toml"
            config_path.write_text(source)
            experiment = load_experiment(config_path)

        self.assertIsInstance(
            experiment.execution_backend, CheckpointExecutionBackend
        )

    def test_conflicting_execution_mode_and_backend_are_rejected(self) -> None:
        source = (EXPERIMENTS_DIR / "register.toml").read_text().replace(
            "[execution]",
            '[execution]\nmode = "gdb"\nbackend = "checkpoint"',
        )

        with TemporaryDirectory(prefix="conflicting-backend-") as directory:
            config_path = Path(directory) / "experiment.toml"
            config_path.write_text(source)
            with self.assertRaisesRegex(ValueError, "must match"):
                load_experiment(config_path)

    def test_checkpoint_mode_rejects_non_gem5_simulator(self) -> None:
        source = (EXPERIMENTS_DIR / "register.toml").read_text()
        source = source.replace(
            'name = "renode"', 'name = "qemu"', 1
        ).replace(
            "[execution]",
            '[execution]\nmode = "checkpoint"',
        )

        with TemporaryDirectory(prefix="checkpoint-experiment-") as directory:
            config_path = Path(directory) / "experiment.toml"
            config_path.write_text(source)
            with self.assertRaisesRegex(ValueError, "requires the gem5 simulator"):
                load_experiment(config_path)

    def test_execution_addresses_are_optional_for_program_symbol_fallback(self) -> None:
        source = (EXPERIMENTS_DIR / "register.toml").read_text()
        source = source.replace("inject_at = 0x80000008\n", "")
        source = source.replace("end_at = 0x8000000c\n", "")

        with TemporaryDirectory(prefix="symbol-address-experiment-") as directory:
            config_path = Path(directory) / "experiment.toml"
            config_path.write_text(source)
            experiment = load_experiment(config_path)

        self.assertIsNone(experiment.injection_address)
        self.assertIsNone(experiment.end_address)

    def test_simulator_names_select_existing_simulator_implementations(self) -> None:
        simulator_types = {
            "gem5": Gem5Simulator,
            "qemu": QemuSimulator,
            "renode": RenodeSimulator,
        }
        source = (EXPERIMENTS_DIR / "register.toml").read_text()

        for name, simulator_type in simulator_types.items():
            with self.subTest(simulator=name):
                with TemporaryDirectory(prefix=f"{name}-experiment-") as directory:
                    config_path = Path(directory) / "experiment.toml"
                    config_path.write_text(source.replace('name = "gem5"', f'name = "{name}"'))
                    experiment = load_experiment(config_path)

                self.assertIsInstance(experiment.simulator, simulator_type)

    def test_memory_toml_builds_memory_fault_injector(self) -> None:
        experiment = load_experiment(EXPERIMENTS_DIR / "memory.toml")

        self.assertIsInstance(experiment.fault_injector, MemoryFaultInjector)
        self.assertEqual(experiment.fault_injector.address, "x5")
        self.assertEqual(experiment.fault_injector.value, 0x11111101)

        gdb = Mock()
        gdb.read_register.return_value = 0x80001000
        experiment.fault_injector.inject(gdb)

        gdb.read_register.assert_called_once_with("x5")
        gdb.write_memory.assert_called_once_with(0x80001000, 0x11111101)

    def test_pc_toml_builds_pc_fault_injector_and_step_option(self) -> None:
        experiment = load_experiment(EXPERIMENTS_DIR / "pc.toml")

        self.assertIsInstance(experiment.fault_injector, PcFaultInjector)
        self.assertEqual(experiment.fault_injector.value, 0x80000010)
        self.assertTrue(experiment.step_after_injection)

    def test_pyrenode_mode_builds_pyrenode_backend_and_fault_injector(self) -> None:
        source = (EXPERIMENTS_DIR / "register.toml").read_text().replace(
            'mode = "gdb"',
            'mode = "pyrenode"',
        )

        with TemporaryDirectory(prefix="pyrenode-experiment-") as directory:
            config_path = Path(directory) / "experiment.toml"
            config_path.write_text(source)
            experiment = load_experiment(config_path)

        self.assertIsInstance(
            experiment.execution_backend, PyRenodeExecutionBackend
        )
        self.assertIsInstance(
            experiment.fault_injector, PyRenodeRegisterFaultInjector
        )

    def test_pyrenode_configurations_resolve_symbols_and_platform(self) -> None:
        expected_injectors = {
            "register": PyRenodeRegisterFaultInjector,
            "memory": PyRenodeMemoryFaultInjector,
            "pc": PyRenodePcFaultInjector,
        }

        for fault, injector_type in expected_injectors.items():
            with self.subTest(fault=fault):
                experiment = load_experiment(
                    EXPERIMENTS_DIR / "pyrenode" / f"{fault}.toml"
                )

                self.assertIsInstance(experiment.fault_injector, injector_type)
                self.assertEqual(
                    experiment.injection_address,
                    experiment.program.fault_injection_point,
                )
                self.assertEqual(experiment.end_address, experiment.program.end_point)
                self.assertEqual(experiment.simulator.config.timeout, 5.0)
                self.assertEqual(
                    experiment.simulator.config.platform,
                    PROJECT_ROOT
                    / "configs"
                    / "simulators"
                    / "renode"
                    / "riscv_min.repl",
                )
                if fault == "pc":
                    self.assertTrue(experiment.step_after_injection)
                    self.assertEqual(
                        experiment.fault_injector.value,
                        experiment.program.resolve_location("end"),
                    )


if __name__ == "__main__":
    unittest.main()
