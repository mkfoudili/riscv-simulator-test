from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import cached_property
from os import PathLike
from pathlib import Path


@dataclass
class TestProgram:
    source: str | PathLike[str]
    elf: str | PathLike[str]

    REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
    PROGRAMS_DIR = REPOSITORY_ROOT / "programs"
    BINARIES_DIR = REPOSITORY_ROOT / "artifacts" / "binaries"

    @property
    def source_path(self) -> Path:
        source = Path(self.source).expanduser()
        if not source.is_absolute() and not source.exists():
            source = self.PROGRAMS_DIR / source
        return source.resolve(strict=True)

    @property
    def elf_path(self) -> Path:
        elf = Path(self.elf).expanduser()
        if not elf.is_absolute():
            binary_path = self.BINARIES_DIR / elf
            if binary_path.exists() or not elf.exists():
                elf = binary_path
        return elf.resolve(strict=True)

    @cached_property
    def _symbols(self) -> dict[str, int]:
        result = subprocess.run(
            ["nm", "-n", "--defined-only", str(self.elf_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        symbols: dict[str, int] = {}
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 3:
                try:
                    symbols[fields[2]] = int(fields[0], 16)
                except ValueError:
                    continue
        return symbols

    def _address(self, symbol: str) -> int:
        try:
            return self._symbols[symbol]
        except KeyError as error:
            raise RuntimeError(
                f"symbol {symbol!r} was not found in {self.elf_path}"
            ) from error

    def resolve_location(self, location: int | str) -> int:
        if isinstance(location, bool):
            raise ValueError("program location must be an address or symbol")
        if isinstance(location, int):
            return location
        try:
            return int(location, 0)
        except ValueError:
            if not location:
                raise ValueError("program location cannot be empty")
            return self._address(location)

    @property
    def entry_point(self) -> int:
        return self._address("_start")

    @property
    def fault_injection_point(self) -> int:
        return self._address("fault_injection_point")

    @property
    def end_point(self) -> int:
        return self._address("end")
