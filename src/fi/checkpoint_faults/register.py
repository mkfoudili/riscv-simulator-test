from __future__ import annotations

from .base import CheckpointEditor, CheckpointFaultInjector


class RegisterCheckpointFaultInjector(CheckpointFaultInjector):
    def __init__(self, register: int, value: int) -> None:
        self.register = register
        self.value = value

    def inject(self, checkpoint: CheckpointEditor, work: str) -> None:
        checkpoint.write_reg(work, self.register, self.value)