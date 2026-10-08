from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from src.fi.execution.pyrenode.session import PyRenodeSession


@dataclass
class FakeRegisterValue:
    RawValue: int

    @classmethod
    def Create(cls, value: int, width: int) -> FakeRegisterValue:
        del width
        return cls(value)


class FakeAddressHook:
    def __init__(self, callback):
        self.callback = callback


@contextmanager
def pyrenode_modules():
    emulation = Mock()
    cpu = Mock()
    bus = Mock()
    machine = Mock()
    machine.sysbus = SimpleNamespace(cpu=cpu)
    machine.sysbus.WriteQuadWord = bus.WriteQuadWord
    emulation.add_mach.return_value = machine
    hooks: dict[int, FakeAddressHook] = {}
    cpu.internal.AddHook.side_effect = lambda address, hook: hooks.__setitem__(
        address, hook
    )

    wrappers = ModuleType("pyrenode3.wrappers")
    wrappers.Emulation = Mock(return_value=emulation)
    antmicro_cpu = ModuleType("Antmicro.Renode.Peripherals.CPU")
    antmicro_cpu.RegisterValue = FakeRegisterValue
    antmicro_cpu.CpuAddressHook = FakeAddressHook
    modules = {
        "pyrenode3": ModuleType("pyrenode3"),
        "pyrenode3.wrappers": wrappers,
        "Antmicro": ModuleType("Antmicro"),
        "Antmicro.Renode": ModuleType("Antmicro.Renode"),
        "Antmicro.Renode.Peripherals": ModuleType("Antmicro.Renode.Peripherals"),
        "Antmicro.Renode.Peripherals.CPU": antmicro_cpu,
    }
    with patch.dict(sys.modules, modules):
        yield emulation, machine, cpu, bus, hooks


class PyRenodeSessionTests(unittest.TestCase):
    def test_creates_emulation_loads_platform_and_runs_to_breakpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory, pyrenode_modules() as (
            emulation,
            machine,
            cpu,
            _bus,
            hooks,
        ):
            elf = Path(directory) / "program.elf"
            platform = Path(directory) / "platform.repl"
            session = PyRenodeSession(elf, platform)
            cpu.PC = FakeRegisterValue(0x80000008)
            emulation.StartAll.side_effect = lambda: hooks[0x80000008].callback(
                cpu, cpu.PC
            )

            session.run_until(0x80000008)
            session.run_until(0x80000008)

            emulation.add_mach.assert_called_once_with("riscv")
            machine.load_repl.assert_called_once_with(str(platform))
            cpu.internal.AddHook.assert_called_once_with(
                0x80000008, hooks[0x80000008]
            )
            self.assertEqual(
                machine.PauseAndRequestEmulationPause.call_count, 2
            )
            self.assertEqual(emulation.PauseAll.call_count, 2)
            self.assertEqual(session.pc(), 0x80000008)

    def test_reset_clears_registers_reloads_elf_and_rearms_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory, pyrenode_modules() as (
            _emulation,
            machine,
            cpu,
            _bus,
            _hooks,
        ):
            elf = Path(directory) / "program.elf"
            session = PyRenodeSession(elf)
            session.add_breakpoint(0x80000008)
            session._breakpoints[0x80000008] = False

            session.reset()

            self.assertEqual(cpu.SetRegisterUnsafe.call_count, 31)
            cpu.SetRegisterUnsafe.assert_any_call(1, FakeRegisterValue(0))
            cpu.SetRegisterUnsafe.assert_any_call(31, FakeRegisterValue(0))
            machine.load_elf.assert_called_once_with(str(elf))
            self.assertTrue(session._breakpoints[0x80000008])

    def test_register_pc_and_memory_access(self) -> None:
        with pyrenode_modules() as (_emulation, _machine, cpu, bus, _hooks):
            session = PyRenodeSession("program.elf")
            cpu.GetRegisterUnsafe.return_value = FakeRegisterValue(0x1234)
            cpu.PC = FakeRegisterValue(0x80000000)

            self.assertEqual(session.read_register("x5"), 0x1234)
            self.assertEqual(session.read_register("pc"), 0x80000000)
            session.write_register("x5", 0x5678)
            cpu.SetRegisterUnsafe.assert_called_once_with(
                5, FakeRegisterValue(0x5678)
            )
            session.write_register("pc", 0x80000010)
            self.assertEqual(cpu.PC.RawValue, 0x80000010)
            session.write_memory(0x80000008, 0x11111101)
            bus.WriteQuadWord.assert_called_once_with(0x80000008, 0x11111101)

    def test_resume_pauses_and_raises_when_no_breakpoint_is_reached(self) -> None:
        with pyrenode_modules() as (emulation, _machine, _cpu, _bus, _hooks):
            session = PyRenodeSession("program.elf", timeout=0)

            with self.assertRaisesRegex(TimeoutError, "no breakpoint reached"):
                session.resume()

            emulation.PauseAll.assert_called_once_with()

    def test_single_step_and_close_use_session_owned_emulation(self) -> None:
        with pyrenode_modules() as (emulation, _machine, cpu, _bus, _hooks):
            session = PyRenodeSession("program.elf")

            session.step_instruction()
            session.close()

            cpu.Step.assert_called_once_with()
            emulation.PauseAll.assert_called_once_with()

    def test_register_names_are_validated(self) -> None:
        with pyrenode_modules() as (_emulation, _machine, _cpu, _bus, _hooks):
            session = PyRenodeSession("program.elf")

            for name in ("r5", "x32", "x-1"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    session.read_register(name)


if __name__ == "__main__":
    unittest.main()
