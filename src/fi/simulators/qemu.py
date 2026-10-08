import os
import subprocess
from pathlib import Path

from .base import Simulator


class QemuSimulator(Simulator):
    REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
    LOG_DIR = REPOSITORY_ROOT / "artifacts" / "logs"
    QEMU_BIN = os.environ.get("QEMU_BIN", "qemu-system-riscv64")

    def start(self, program: str | os.PathLike[str]) -> None:
        elf = self.resolve_program(program)
        endpoint = self.gdb_endpoint
        log_path = self.LOG_DIR / f"qemu_{elf.name}.log"
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        with log_path.open("w") as log:
            self.process = subprocess.Popen(
                [
                    self.QEMU_BIN,
                    "-machine",
                    "virt",
                    "-nographic",
                    "-bios",
                    "none",
                    "-kernel",
                    str(elf),
                    "-S",
                    "-gdb",
                    f"tcp:{endpoint.host}:{endpoint.port}",
                ],
                cwd=elf.parent,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

    def stop(self) -> None:
        self._stop_process()