from __future__ import annotations

from typing import TYPE_CHECKING

from .base import GDBFaultInjector

if TYPE_CHECKING:
    from ..gdb.client import GdbClient


class MemoryFaultInjector(GDBFaultInjector):

    def __init__(self, address: int | str, value: int) -> None:
        self.address = address
        self.value = value

    def inject(self, gdb: GdbClient) -> None:
        address = (
            gdb.read_register(self.address)
            if isinstance(self.address, str)
            else self.address
        )
        gdb.write_memory(
            address,
            self.value,
        )