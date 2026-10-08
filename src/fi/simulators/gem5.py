import os
import subprocess

from .base import Simulator


class Gem5Simulator(Simulator):
    GEM5_SCRIPT = Simulator.REPOSITORY_ROOT / "gdb_gem5.py"
    GEM5_CWD = GEM5_SCRIPT.parent
    LOG_DIR = Simulator.REPOSITORY_ROOT / "artifacts" / "logs"
    GEM5_OUTPUT_DIR = Simulator.REPOSITORY_ROOT / "artifacts" / "gem5"
    GEM5_BIN = os.environ.get(
        "GEM5_BIN", "/home/khadidja/gem5/build/RISCV/gem5.opt"
    )

    def start(self, program: str | os.PathLike[str]) -> None:
        elf = self.resolve_program(program)
        endpoint = self.gdb_endpoint
        outdir = self.GEM5_OUTPUT_DIR / f"m5out_{elf.name}"
        log_path = self.LOG_DIR / f"gem5_{elf.name}.log"
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.GEM5_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with log_path.open("w") as log:
            self.process = subprocess.Popen(
                [
                    self.GEM5_BIN,
                    "--listener-mode=on",
                    f"--remote-gdb-port={endpoint.port}",
                    f"--outdir={outdir}",
                    str(self.GEM5_SCRIPT),
                    "--elf",
                    str(elf),
                ],
                cwd=self.GEM5_CWD,
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

    def stop(self) -> None:
        self._stop_process()