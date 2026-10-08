import os
import re
import time
from pathlib import Path
from typing import Any

from pygdbmi.gdbcontroller import GdbController

from ..config.simulator import SimulatorConfig


class GdbClient:
    CONNECTION_ATTEMPTS = 40
    CONNECTION_RETRY_DELAY = 0.5
    MEMORY_WORD_SIZE = 8
    GDB_BIN = os.environ.get("GDB_BIN", "gdb-multiarch")

    def __init__(self, config: SimulatorConfig) -> None:
        self.config = config
        self._controller: GdbController | None = None

    def start(self, program: str | os.PathLike[str]) -> None:
        if self._controller is not None:
            raise RuntimeError("GDB is already running")

        elf = Path(program).expanduser().resolve(strict=True)
        self._controller = GdbController(
            command=[
                self.GDB_BIN,
                "--interpreter=mi3",
                "--quiet",
                str(elf),
            ]
        )
        try:
            self._write("set architecture riscv:rv64")
        except Exception:
            self.close()
            raise

    def connect(self, host: str, port: int) -> None:
        controller = self._require_started()
        if not host:
            raise ValueError("GDB endpoint host must not be empty")
        if not 1 <= port <= 65535:
            raise ValueError(f"invalid GDB endpoint port: {port}")

        target = f"{host}:{port}"
        last_error = "no successful connection response"
        for attempt in range(self.CONNECTION_ATTEMPTS):
            responses = controller.write(
                f"-target-select remote {target}",
                timeout_sec=self.config.timeout,
            )
            if any(
                response.get("type") == "result"
                and response.get("message") == "connected"
                for response in responses
            ):
                return

            error = self._result_error(responses)
            if error is not None:
                last_error = error
            if attempt + 1 < self.CONNECTION_ATTEMPTS:
                time.sleep(self.CONNECTION_RETRY_DELAY)

        raise RuntimeError(f"could not connect to GDB server at {target}: {last_error}")

    def continue_execution(self) -> None:
        self._execute_until_stopped("-exec-continue")

    def step_instruction(self) -> None:
        self._execute_until_stopped("-exec-step-instruction")

    def _execute_until_stopped(self, command: str) -> None:
        controller = self._require_started()
        responses = self._write(command)
        while not self._has_stopped(responses):
            responses = controller.get_gdb_response(timeout_sec=self.config.timeout)
            self._raise_for_result_error(responses)

    def set_breakpoint(self, address: int) -> None:
        self._write(f"-break-insert *{address:#x}")

    def read_register(self, register: str) -> int:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", register):
            raise ValueError(f"invalid register name: {register!r}")
        responses = self._write(f'-data-evaluate-expression "${register}"')
        value = self._result_payload_value(responses)
        try:
            return int(value, 0)
        except ValueError as error:
            raise RuntimeError(
                f"GDB returned a non-integer value for register {register}: {value!r}"
            ) from error

    def write_register(self, register: str, value: int) -> None:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", register):
            raise ValueError(f"invalid register name: {register!r}")
        self._write(f'-data-evaluate-expression "${register} = {value:#x}"')

    def read_memory(self, address: int) -> int:
        responses = self._write(
            f"-data-read-memory-bytes {address:#x} {self.MEMORY_WORD_SIZE}"
        )
        result = self._result_payload(responses)
        memory = result.get("memory")
        if not isinstance(memory, list) or not memory:
            raise RuntimeError("GDB returned no data for the requested memory address")

        contents = "".join(
            block.get("contents", "")
            for block in memory
            if isinstance(block, dict)
        )
        try:
            data = bytes.fromhex(contents)
        except ValueError as error:
            raise RuntimeError(
                f"GDB returned invalid memory contents: {contents!r}"
            ) from error
        if len(data) != self.MEMORY_WORD_SIZE:
            raise RuntimeError(
                f"GDB returned {len(data)} bytes; expected {self.MEMORY_WORD_SIZE}"
            )
        return int.from_bytes(data, byteorder="little")

    def write_memory(self, address: int, value: int) -> None:
        data = value.to_bytes(self.MEMORY_WORD_SIZE, byteorder="little")
        self._write(f"-data-write-memory-bytes {address:#x} {data.hex()}")

    def set_pc(self, address: int) -> None:
        self.write_register("pc", address)

    def close(self) -> None:
        if self._controller is None:
            return

        controller = self._controller
        self._controller = None
        controller.exit()

    def _require_started(self) -> GdbController:
        if self._controller is None:
            raise RuntimeError("GDB has not been started")
        return self._controller

    def _write(self, command: str) -> list[dict[str, Any]]:
        responses = self._require_started().write(
            command,
            timeout_sec=self.config.timeout,
        )
        self._raise_for_result_error(responses)
        return responses

    @staticmethod
    def _result_error(responses: list[dict[str, Any]]) -> str | None:
        for response in responses:
            if response.get("type") == "result" and response.get("message") == "error":
                payload = response.get("payload", {})
                if isinstance(payload, dict):
                    message = payload.get("msg")
                    if isinstance(message, str):
                        return message
                return "GDB reported an unspecified command error"
        return None

    @classmethod
    def _raise_for_result_error(cls, responses: list[dict[str, Any]]) -> None:
        error = cls._result_error(responses)
        if error is not None:
            raise RuntimeError(f"GDB command failed: {error}")

    @staticmethod
    def _result_payload(responses: list[dict[str, Any]]) -> dict[str, Any]:
        for response in responses:
            if response.get("type") == "result" and response.get("message") == "done":
                payload = response.get("payload")
                if isinstance(payload, dict):
                    return payload
        raise RuntimeError("GDB returned no successful command result")

    @classmethod
    def _result_payload_value(cls, responses: list[dict[str, Any]]) -> str:
        payload = cls._result_payload(responses)
        value = payload.get("value")
        if not isinstance(value, str):
            raise RuntimeError("GDB returned no value for the requested expression")
        return value

    @staticmethod
    def _has_stopped(responses: list[dict[str, Any]]) -> bool:
        return any(
            response.get("type") == "notify"
            and response.get("message") == "stopped"
            for response in responses
        )
