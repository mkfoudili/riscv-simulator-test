from __future__ import annotations

import unittest
from unittest.mock import Mock

from src.fi.pyrenode_faults.memory import MemoryFaultInjector
from src.fi.pyrenode_faults.pc import PcFaultInjector
from src.fi.pyrenode_faults.register import RegisterFaultInjector


class PyRenodeFaultInjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Mock()

    def test_register_fault_writes_configured_register_value(self) -> None:
        injector = RegisterFaultInjector("x5", 0x11111101)

        injector.inject(self.session)

        self.session.write_register.assert_called_once_with("x5", 0x11111101)

    def test_memory_fault_uses_register_value_as_address(self) -> None:
        self.session.read_register.return_value = 0x80001000
        injector = MemoryFaultInjector("x5", 0x11111101)

        injector.inject(self.session)

        self.session.read_register.assert_called_once_with("x5")
        self.session.write_memory.assert_called_once_with(
            0x80001000, 0x11111101
        )

    def test_memory_fault_accepts_a_literal_address(self) -> None:
        injector = MemoryFaultInjector(0x80001000, 0x11111101)

        injector.inject(self.session)

        self.session.read_register.assert_not_called()
        self.session.write_memory.assert_called_once_with(
            0x80001000, 0x11111101
        )

    def test_pc_fault_sets_configured_program_counter(self) -> None:
        injector = PcFaultInjector(0x80000010)

        injector.inject(self.session)

        self.session.set_pc.assert_called_once_with(0x80000010)


if __name__ == "__main__":
    unittest.main()
