from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..gdb.client import GdbClient


class GDBFaultInjector(ABC):

    @abstractmethod
    def inject(self, gdb: GdbClient) -> None:
        raise NotImplementedError