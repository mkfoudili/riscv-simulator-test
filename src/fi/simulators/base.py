from abc import ABC, abstractmethod
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.simulator import SimulatorConfig


@dataclass(frozen=True)
class GdbEndpoint:
    host: str
    port: int


class Simulator(ABC):
    REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
    BINARIES_DIR = REPOSITORY_ROOT / "artifacts" / "binaries"

    def __init__(self, config: SimulatorConfig):
        self.config = config
        self.process: subprocess.Popen[bytes] | None = None

    @abstractmethod
    def start(self, program: str | os.PathLike[str]) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @property
    def gdb_endpoint(self) -> GdbEndpoint:
        return GdbEndpoint(self.config.host, self.config.port)

    def prepare(self, program: str | os.PathLike[str]) -> None:
        self.resolve_program(program)

    def cleanup(self) -> None:
        pass

    def resolve_program(self, program: str | os.PathLike[str]) -> Path:
        path = Path(program).expanduser()
        if not path.is_absolute():
            binary_path = self.BINARIES_DIR / path
            if binary_path.exists() or not path.exists():
                path = binary_path
        return path.resolve(strict=True)

    def _stop_process(self) -> None:
        if self.process is None:
            return

        if self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=self.config.timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.process.wait()
        else:
            self.process.wait()
        self.process = None

    def run(self, program: str | os.PathLike[str], experiment: Any) -> Any:
        try:
            self.prepare(program)
            self.start(program)
            return experiment.execute(self)
        finally:
            try:
                self.stop()
            finally:
                self.cleanup()