from __future__ import annotations

import unittest
from unittest.mock import Mock

from src.fi.checkpoint_faults.memory import MemoryCheckpointFaultInjector
from src.fi.checkpoint_faults.pc import PcCheckpointFault
from src.fi.checkpoint_faults.register import RegisterCheckpointFaultInjector


class CheckpointFaultInjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.checkpoint = Mock()

    def test_register_fault_writes_selected_register(self) -> None:
        injector = RegisterCheckpointFaultInjector(register=5, value=0x11111101)

        injector.inject(self.checkpoint, "checkpoint")

        self.checkpoint.write_reg.assert_called_once_with(
            "checkpoint", 5, 0x11111101
        )

    def test_memory_fault_writes_eight_little_endian_bytes(self) -> None:
        self.checkpoint.read_reg.return_value = 0x80001000
        injector = MemoryCheckpointFaultInjector(
            address_register=5,
            value=0x11111101,
        )

        injector.inject(self.checkpoint, "checkpoint")

        self.checkpoint.read_reg.assert_called_once_with("checkpoint", 5)
        self.checkpoint.write_mem.assert_called_once_with(
            "checkpoint",
            0x80001000,
            b"\x01\x11\x11\x11\x00\x00\x00\x00",
        )

    def test_pc_fault_writes_configured_program_counter(self) -> None:
        injector = PcCheckpointFault(value=0x80000010)

        injector.inject(self.checkpoint, "checkpoint")

        self.checkpoint.write_pc.assert_called_once_with(
            "checkpoint", 0x80000010
        )


if __name__ == "__main__":
    unittest.main()
