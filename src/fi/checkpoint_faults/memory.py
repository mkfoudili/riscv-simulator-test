from __future__ import annotations

from .base import CheckpointEditor, CheckpointFaultInjector


class MemoryCheckpointFaultInjector(CheckpointFaultInjector):
    def __init__(self, address_register: int, value: int) -> None:
        self.address_register = address_register
        self.value = value

    def inject(self, checkpoint: CheckpointEditor, work: str) -> None:
        address = checkpoint.read_reg(work, self.address_register)
        checkpoint.write_mem(work, address, self.value.to_bytes(8, "little"))