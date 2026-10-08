from __future__ import annotations

from typing import TYPE_CHECKING

from .base import PyRenodeFaultInjector

if TYPE_CHECKING:
    from ..execution.pyrenode.session import PyRenodeSession


class PcFaultInjector(PyRenodeFaultInjector):
    def __init__(self, value: int) -> None:
        self.value = value

    def inject(self, session: PyRenodeSession) -> None:
        session.set_pc(self.value)
