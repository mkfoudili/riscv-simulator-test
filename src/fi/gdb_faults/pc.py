from __future__ import annotations

from typing import TYPE_CHECKING

from .base import GDBFaultInjector

if TYPE_CHECKING:
    from ..gdb.client import GdbClient


class PcFaultInjector(GDBFaultInjector):

    def __init__(self, value: int) -> None:
        self.value = value

    def inject(self, gdb: GdbClient) -> None:
        gdb.set_pc(self.value)