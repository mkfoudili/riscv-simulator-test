from __future__ import annotations

from .base import CheckpointEditor, CheckpointFaultInjector


class PcCheckpointFault(CheckpointFaultInjector):
    def __init__(self, value: int) -> None:
        self.value = value

    def inject(self, checkpoint: CheckpointEditor, work: str) -> None:
        checkpoint.write_pc(work, self.value)