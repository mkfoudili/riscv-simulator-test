import os
import subprocess
import tempfile
from pathlib import Path

from ..config.simulator import SimulatorConfig
from .base import Simulator


class RenodeSimulator(Simulator):
    REPOSITORY_ROOT = Simulator.REPOSITORY_ROOT
    RENODE_CONFIG_DIR = REPOSITORY_ROOT / "configs" / "simulators" / "renode"
    BUILD_DIR = REPOSITORY_ROOT / "build"
    LOG_DIR = REPOSITORY_ROOT / "artifacts" / "logs"
    RENODE_BIN = os.environ.get("RENODE_BIN", "renode")

    def __init__(self, config: SimulatorConfig):
        super().__init__(config)
        self._boot_file: Path | None = None

    def start(self, program: str | os.PathLike[str]) -> None:
        elf = self.resolve_program(program)
        endpoint = self.gdb_endpoint
        gdb_script_path = self.RENODE_CONFIG_DIR / "gdb.resc"
        gdb_script = gdb_script_path.read_text()
        port_directive = "machine StartGdbServer 1234"
        if port_directive not in gdb_script:
            raise RuntimeError(f"could not configure Renode GDB port in {gdb_script_path}")
        gdb_script = gdb_script.replace(
            port_directive,
            f"machine StartGdbServer {endpoint.port}",
        )

        self.BUILD_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".boot_{elf.name}_",
            suffix=".resc",
            dir=self.BUILD_DIR,
            delete=False,
        ) as boot_file:
            self._boot_file = Path(boot_file.name)
            boot_file.write(f"$elf=@{elf}\n")
            boot_file.write(gdb_script)

        log_path = self.LOG_DIR / f"renode_{elf.name}.log"
        with log_path.open("w") as log:
            self.process = subprocess.Popen(
                [self.RENODE_BIN, "--disable-xwt", "--console", str(self._boot_file)],
                cwd=self.RENODE_CONFIG_DIR,
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

    def stop(self) -> None:
        try:
            self._stop_process()
        finally:
            if self._boot_file is not None:
                self._boot_file.unlink(missing_ok=True)
                self._boot_file = None