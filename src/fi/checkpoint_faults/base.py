from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol


class CheckpointEditor(Protocol):
    def read_reg(self, directory: str, number: int) -> int: ...

    def write_reg(self, directory: str, number: int, value: int) -> None: ...

    def write_pc(self, directory: str, pc: int) -> None: ...

    def write_mem(self, directory: str, vaddr: int, data: bytes) -> None: ...


class CheckpointFaultInjector(ABC):
    @abstractmethod
    def inject(self, checkpoint: CheckpointEditor, work: str) -> None:
        raise NotImplementedError