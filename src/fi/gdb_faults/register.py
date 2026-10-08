from __future__ import annotations

from typing import TYPE_CHECKING

from .base import GDBFaultInjector

if TYPE_CHECKING:
    from ..gdb.client import GdbClient


class RegisterFaultInjector(GDBFaultInjector):

    def __init__(self, register: str, value: int) -> None:
        self.register = register
        self.value = value

    def inject(self, gdb: GdbClient) -> None:
        gdb.write_register(
            self.register,
            self.value,
        )