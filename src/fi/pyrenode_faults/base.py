from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..execution.pyrenode.session import PyRenodeSession


class PyRenodeFaultInjector(ABC):
    @abstractmethod
    def inject(self, session: PyRenodeSession) -> None:
        raise NotImplementedError
