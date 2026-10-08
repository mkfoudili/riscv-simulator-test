from __future__ import annotations

import gzip
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from elftools.elf.elffile import ELFFile

from src.fi.checkpoint_faults.memory import MemoryCheckpointFaultInjector
from src.fi.checkpoint_faults.pc import PcCheckpointFault
from src.fi.checkpoint_faults.register import RegisterCheckpointFaultInjector
from src.fi.execution.checkpoint.workspace import Workspace
from src.fi.execution.checkpoint_execution import CheckpointExecutionBackend
from src.fi.execution.checkpoint.state import CheckpointState
from src.fi.experiments.experiment import Experiment
from src.fi.experiments.result import Result
from src.fi.program import TestProgram


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ELF = PROJECT_ROOT / "artifacts" / "binaries" / "register_test.elf"
CHECKPOINT_SCRIPT = (
    PROJECT_ROOT / "configs" / "simulators" / "gem5" / "gem5_ckpt.py"
)
MEMORY_FAULT_VALUE = 0x11111101


class CheckpointExecutionIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="checkpoint-integration-"
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.artifacts_root = Path(self.temporary_directory.name) / "artifacts"
        self.commands: list[list[str]] = []
        self.workspace = Workspace(
            root=self.artifacts_root / "gem5" / "checkpoints",
            gem5="fake-gem5",
            checkpoint_script=CHECKPOINT_SCRIPT,
        )
        self.program = TestProgram(source="register_test.S", elf=TEST_ELF)
        with TEST_ELF.open("rb") as elf_file:
            load_segment = next(
                segment
                for segment in ELFFile(elf_file).iter_segments()
                if segment["p_type"] == "PT_LOAD" and len(segment.data()) >= 64
            )
            self.load_segment_data = load_segment.data()
            self.load_segment_vaddr = load_segment["p_vaddr"]

    def _experiment(
        self,
        fault_injector,
        *,
        step_after_injection: bool = False,
    ) -> Experiment:
        return Experiment(
            simulator=SimpleNamespace(),
            program=self.program,
            fault_injector=fault_injector,
            output_register="x10",
            step_after_injection=step_after_injection,
            injection_address=0x80000008,
            end_address=0x80000010,
            execution_backend=CheckpointExecutionBackend(self.workspace),
        )

    def _fake_gem5(self):
        def run(command, **kwargs):
            self.assertEqual(kwargs["capture_output"], True)
            self.assertEqual(kwargs["text"], True)
            self.commands.append(command)
            options = {
                command[index]: command[index + 1]
                for index in range(1, len(command) - 1)
                if command[index].startswith("--")
            }
            save_to = Path(options["--save-to"])
            save_to.mkdir(parents=True, exist_ok=True)
            restore_from = options.get("--restore-from")
            if restore_from is None:
                registers = [0] * 32
                registers[5] = self.load_segment_vaddr
                registers[10] = 0x1234
                (save_to / "m5.cpt").write_text(
                    "[system.cpu.threads.thread0.xc.0]\n"
                    f"regs.integer={' '.join(map(str, registers))}\n"
                    "_pc=2147483652\n"
                    "_npc=2147483656\n"
                )
                pmem = b"prefix!" + self.load_segment_data + b"suffix"
                with gzip.open(save_to / "board.physmem.store0.pmem", "wb") as f:
                    f.write(pmem)
            else:
                shutil.copytree(restore_from, save_to, dirs_exist_ok=True)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        return run

    def _run(self, fault_injector, *, step_after_injection: bool = False):
        experiment = self._experiment(
            fault_injector,
            step_after_injection=step_after_injection,
        )
        with patch(
            "src.fi.execution.checkpoint.runner.subprocess.run",
            side_effect=self._fake_gem5(),
        ):
            result = experiment.run()
        return result

    def test_register_fault_executes_full_checkpoint_trial_under_artifacts(self):
        result = self._run(
            RegisterCheckpointFaultInjector(5, MEMORY_FAULT_VALUE)
        )

        self.assertIs(result, Result.NO_EFFECT)
        experiment_root = (
            self.artifacts_root
            / "gem5"
            / "checkpoints"
            / f"fi_{TEST_ELF.name}"
        )
        self.assertEqual(len(self.commands), 3)
        self.assertTrue((experiment_root / "final_golden" / "m5.cpt").is_file())
        self.assertTrue((experiment_root / "final_faulty" / "m5.cpt").is_file())
        state = CheckpointState(str(TEST_ELF), self.workspace)
        self.assertEqual(state.read_reg(experiment_root / "ckpt_faulty", 5), MEMORY_FAULT_VALUE)
        self.assertTrue(
            all(
                Path(command[1].removeprefix("--outdir=")).is_relative_to(
                    self.artifacts_root
                )
                for command in self.commands
            )
        )

    def test_pc_fault_resumes_faulty_trial_at_configured_pc(self):
        target_pc = 0x80000010
        result = self._run(
            PcCheckpointFault(target_pc),
            step_after_injection=True,
        )

        self.assertIs(result, Result.NO_EFFECT)
        last_command = self.commands[-1]
        self.assertEqual(
            last_command[last_command.index("--stop-pc") + 1],
            hex(target_pc),
        )
        experiment_root = (
            self.artifacts_root
            / "gem5"
            / "checkpoints"
            / f"fi_{TEST_ELF.name}"
        )
        state = CheckpointState(str(TEST_ELF), self.workspace)
        faulty_lines = state._load(experiment_root / "ckpt_faulty")
        self.assertEqual(
            state._get_key(faulty_lines, r"\.xc\.0\]$", "_pc"),
            str(target_pc),
        )
        self.assertEqual(
            state._get_key(faulty_lines, r"\.xc\.0\]$", "_npc"),
            str(target_pc + 4),
        )
    def test_memory_fault_updates_checkpoint_pmem(self):
        result = self._run(
            MemoryCheckpointFaultInjector(5, MEMORY_FAULT_VALUE)
        )

        self.assertIs(result, Result.NO_EFFECT)
        experiment_root = (
            self.artifacts_root
            / "gem5"
            / "checkpoints"
            / f"fi_{TEST_ELF.name}"
        )
        with gzip.open(
            experiment_root
            / "ckpt_faulty"
            / "board.physmem.store0.pmem",
            "rb",
        ) as memory_file:
            pmem = memory_file.read()
        address_offset = len(b"prefix!")
        self.assertEqual(
            pmem[address_offset:address_offset + 8],
            MEMORY_FAULT_VALUE.to_bytes(8, "little"),
        )


if __name__ == "__main__":
    unittest.main()
