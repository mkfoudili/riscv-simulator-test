from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from src.fi.config.experiment import load_experiment
from src.fi.experiments.result import Result
from src.fi.faults.base import GDBFaultInjector
from src.fi.faults.register import RegisterFaultInjector
from src.fi.gdb.client import GdbClient
from src.fi.simulators.gem5 import Gem5Simulator
from src.fi.simulators.qemu import QemuSimulator
from src.fi.simulators.renode import RenodeSimulator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTER_TEST_SOURCE = PROJECT_ROOT / "programs" / "register_test.S"
INITIAL_REGISTER_VALUE = 0x11111111


class _RegisterWriteCheck(GDBFaultInjector):
    def __init__(
        self,
        test_case: unittest.TestCase,
        configured_injector: GDBFaultInjector,
        expected_register_value: int,
    ) -> None:
        self.test_case = test_case
        self.configured_injector = configured_injector
        self.expected_register_value = expected_register_value
        self.called = False

    def inject(self, gdb: GdbClient) -> None:
        self.called = True
        self.test_case.assertEqual(
            gdb.read_register("x5"),
            INITIAL_REGISTER_VALUE,
            "the program should execute its initialization before the breakpoint",
        )
        self.configured_injector.inject(gdb)
        self.test_case.assertEqual(
            gdb.read_register("x5"),
            self.expected_register_value,
            "the configured register fault should be applied",
        )


class SimulatorGdbIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler_name = os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc")
        compiler = shutil.which(compiler_name)
        if compiler is None:
            raise unittest.SkipTest(
                f"RISC-V compiler {compiler_name!r} is unavailable; "
                "set RISCV_CC to a RISC-V GCC executable"
            )

        cls._temporary_directory = tempfile.TemporaryDirectory(
            prefix="riscv-gdb-integration-"
        )
        cls.addClassCleanup(cls._temporary_directory.cleanup)
        temporary_name = Path(cls._temporary_directory.name).name
        cls.elf_path = Path(cls._temporary_directory.name) / f"{temporary_name}.elf"
        subprocess.run(
            [
                compiler,
                "-nostdlib",
                "-nostartfiles",
                "-static",
                "-march=rv64imafd",
                "-Wl,--build-id=none",
                "-Wl,-Ttext=0x80000000",
                "-Wl,-e,_start",
                "-o",
                str(cls.elf_path),
                str(REGISTER_TEST_SOURCE),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def _assert_experiment_runs(
        self,
        simulator_name: str,
        executable: str,
    ) -> None:
        if shutil.which(executable) is None:
            self.skipTest(
                f"{simulator_name} executable {executable!r} is unavailable"
            )

        base_config = (
            PROJECT_ROOT / "configs" / "experiments" / "register.toml"
        ).read_text()
        configured_port = tomllib.loads(base_config)["simulator"]["port"]
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if simulator_name == "gem5":
                port = configured_port
                try:
                    listener.bind(("127.0.0.1", port))
                except OSError:
                    self.skipTest(f"gem5 GDB port {port} is already in use")
            else:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]

        with tempfile.TemporaryDirectory(prefix="riscv-gdb-config-") as directory:
            config_path = Path(directory) / "register.toml"
            replacements = (
                ('name = "gem5"', f'name = "{simulator_name}"'),
                (
                    'elf = "register_test.elf"',
                    f"elf = {json.dumps(str(self.elf_path))}",
                ),
                (f"port = {configured_port}", f"port = {port}"),
                (
                    "[simulator]\nname =",
                    '[simulator]\nhost = "127.0.0.1"\ntimeout = 10.0\nname =',
                ),
            )
            config_text = base_config
            for old, new in replacements:
                self.assertEqual(
                    config_text.count(old),
                    1,
                    f"expected one {old!r} entry in register.toml",
                )
                config_text = config_text.replace(old, new, 1)
            config_path.write_text(config_text)
            experiment = load_experiment(config_path)

        simulator_types = {
            "qemu": QemuSimulator,
            "gem5": Gem5Simulator,
            "renode": RenodeSimulator,
        }
        self.assertIsInstance(experiment.simulator, simulator_types[simulator_name])
        self.assertEqual(experiment.simulator.config.host, "127.0.0.1")
        self.assertEqual(experiment.simulator.config.port, port)
        self.assertEqual(experiment.simulator.config.timeout, 10.0)
        self.assertEqual(experiment.program.source_path, REGISTER_TEST_SOURCE.resolve())
        self.assertEqual(experiment.program.elf_path, self.elf_path)
        self.assertEqual(
            experiment.injection_address,
            experiment.program.fault_injection_point,
        )
        self.assertEqual(experiment.end_address, experiment.program.end_point)
        self.assertEqual(experiment.output_register, "x10")
        configured_injector = experiment.fault_injector
        if not isinstance(configured_injector, RegisterFaultInjector):
            self.fail("register.toml did not create a register fault injector")
        self.assertEqual(configured_injector.register, "x5")
        expected_register_value = configured_injector.value
        injector = _RegisterWriteCheck(
            self,
            configured_injector,
            expected_register_value,
        )
        experiment.fault_injector = injector

        result = experiment.run()

        self.assertTrue(injector.called, "the fault-injection breakpoint was not hit")
        self.assertIs(
            result,
            Result.SILENT_DATA_CORRUPTION,
            "the program should continue to its end breakpoint and expose the "
            "modified register value through x10",
        )

    def test_qemu_gdb_integration(self) -> None:
        self._assert_experiment_runs("qemu", QemuSimulator.QEMU_BIN)

    def test_gem5_gdb_integration(self) -> None:
        self._assert_experiment_runs("gem5", Gem5Simulator.GEM5_BIN)

    def test_renode_gdb_integration(self) -> None:
        self._assert_experiment_runs("renode", RenodeSimulator.RENODE_BIN)


if __name__ == "__main__":
    unittest.main()
