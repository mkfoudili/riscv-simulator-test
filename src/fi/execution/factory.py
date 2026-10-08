from __future__ import annotations

from ..simulators.base import Simulator
from ..simulators.gem5 import Gem5Simulator
from ..simulators.renode import RenodeSimulator
from .base import ExecutionBackend
from .checkpoint_execution import CheckpointExecutionBackend
from .gdb_execution import GdbExecutionBackend
from .pyrenode.backend import PyRenodeExecutionBackend


class ExecutionBackendFactory:
    @staticmethod
    def create(mode: str, simulator: Simulator) -> ExecutionBackend:
        if mode == "gdb":
            return GdbExecutionBackend()
        if mode == "checkpoint":
            if not isinstance(simulator, Gem5Simulator):
                raise ValueError("checkpoint execution requires the gem5 simulator")
            return CheckpointExecutionBackend()
        if mode == "pyrenode":
            if not isinstance(simulator, RenodeSimulator):
                raise ValueError("pyrenode execution requires the renode simulator")
            return PyRenodeExecutionBackend()
        raise ValueError(f"unsupported execution backend: {mode!r}")