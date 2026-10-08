from __future__ import annotations

from typing import TYPE_CHECKING

from .base import PyRenodeFaultInjector

if TYPE_CHECKING:
    from ..execution.pyrenode.session import PyRenodeSession


class RegisterFaultInjector(PyRenodeFaultInjector):
    def __init__(self, register: str, value: int) -> None:
        self.register = register
        self.value = value

    def inject(self, session: PyRenodeSession) -> None:
        session.write_register(self.register, self.value)
