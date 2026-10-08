from __future__ import annotations

from typing import TYPE_CHECKING

from .base import PyRenodeFaultInjector

if TYPE_CHECKING:
    from ..execution.pyrenode.session import PyRenodeSession


class MemoryFaultInjector(PyRenodeFaultInjector):
    def __init__(self, address: int | str, value: int) -> None:
        self.address = address
        self.value = value

    def inject(self, session: PyRenodeSession) -> None:
        address = (
            session.read_register(self.address)
            if isinstance(self.address, str)
            else self.address
        )
        session.write_memory(address, self.value)
