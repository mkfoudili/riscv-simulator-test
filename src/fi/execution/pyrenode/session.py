from __future__ import annotations

import threading
from os import PathLike
from pathlib import Path


class PyRenodeSession:
    REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
    DEFAULT_PLATFORM = (
        REPOSITORY_ROOT / "configs" / "simulators" / "renode" / "riscv_min.repl"
    )

    def __init__(
        self,
        elf: str | PathLike[str],
        platform: str | PathLike[str] | None = None,
        timeout: float = 5.0,
    ) -> None:
        from pyrenode3.wrappers import Emulation
        from Antmicro.Renode.Peripherals.CPU import CpuAddressHook, RegisterValue

        self._register_value = RegisterValue
        self._cpu_address_hook = CpuAddressHook
        self._elf = Path(elf).expanduser().resolve()
        self._timeout = timeout
        platform_path = platform if platform is not None else self.DEFAULT_PLATFORM
        self._emulation = Emulation()
        self._machine = self._emulation.add_mach("riscv")
        self._machine.load_repl(str(Path(platform_path).expanduser().resolve()))
        self._cpu = self._machine.sysbus.cpu
        self._bus = self._machine.sysbus
        self._stopped = threading.Event()
        self._breakpoints: dict[int, bool] = {}
        self._hooked_addresses: set[int] = set()
        self._hooks: list[object] = []
        self._hit_address: int | None = None

    def add_breakpoint(self, address: int) -> None:
        self._breakpoints[address] = True
        if address in self._hooked_addresses:
            return

        def on_hit(_cpu: object, _pc: object) -> None:
            if self._breakpoints[address]:
                self._breakpoints[address] = False
                self._hit_address = address
                self._stopped.set()
                self._machine.PauseAndRequestEmulationPause()

        hook = self._cpu_address_hook(on_hit)
        self._hooks.append(hook)
        self._cpu.internal.AddHook(address, hook)
        self._hooked_addresses.add(address)

    def reset(self) -> None:
        for register in range(1, 32):
            self._set_register(register, 0)
        self._machine.load_elf(str(self._elf))
        for address in self._breakpoints:
            self._breakpoints[address] = True
        self._hit_address = None

    def resume(self) -> None:
        self._stopped.clear()
        self._emulation.StartAll()
        if not self._stopped.wait(self._timeout):
            self._emulation.PauseAll()
            raise TimeoutError("no breakpoint reached (hang?)")
        self._emulation.PauseAll()
        if self.pc() != self._hit_address:
            raise RuntimeError(
                f"stopped at {self.pc():#x} instead of breakpoint "
                f"{self._hit_address:#x}"
            )

    def step_instruction(self) -> None:
        self._cpu.Step()

    def close(self) -> None:
        self._emulation.PauseAll()

    def run_until(self, address: int) -> None:
        self.add_breakpoint(address)
        self.resume()

    def _set_register(self, number: int, value: int) -> None:
        self._cpu.SetRegisterUnsafe(
            number, self._register_value.Create(value, 64)
        )

    @staticmethod
    def _register_number(name: str) -> int:
        if not name.startswith("x") or not name[1:].isdigit():
            raise ValueError(f"invalid RISC-V register name: {name!r}")
        number = int(name[1:])
        if not 0 <= number <= 31:
            raise ValueError(f"register is out of range: {name!r}")
        return number

    def read_register(self, name: str) -> int:
        if name.lower() == "pc":
            return self.pc()
        return int(self._cpu.GetRegisterUnsafe(self._register_number(name)).RawValue)

    def write_register(self, name: str, value: int) -> None:
        if name.lower() == "pc":
            self.set_pc(value)
            return
        self._set_register(self._register_number(name), value)

    def pc(self) -> int:
        return int(self._cpu.PC.RawValue)

    def set_pc(self, value: int) -> None:
        self._cpu.PC = self._register_value.Create(value, 64)

    def write_memory(self, address: int, value: int) -> None:
        self._bus.WriteQuadWord(address, value)
