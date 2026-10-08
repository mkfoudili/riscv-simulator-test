from abc import ABC, abstractmethod
from typing import Any


class ExecutionBackend(ABC):

    @abstractmethod
    def execute(self, experiment: Any) -> Any:
        raise NotImplementedError