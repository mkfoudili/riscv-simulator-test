from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..experiments.experiment import Experiment
from ..execution.factory import ExecutionBackendFactory
from ..faults.memory import MemoryFaultInjector
from ..faults.pc import PcFaultInjector
from ..faults.register import RegisterFaultInjector
from ..pyrenode_faults.memory import MemoryFaultInjector as PyRenodeMemoryFaultInjector
from ..pyrenode_faults.pc import PcFaultInjector as PyRenodePcFaultInjector
from ..pyrenode_faults.register import (
    RegisterFaultInjector as PyRenodeRegisterFaultInjector,
)
from ..program import TestProgram
from ..simulators.factory import SimulatorFactory
from .simulator import SimulatorConfig

if TYPE_CHECKING:
    from ..execution.base import ExecutionBackend
    from ..faults.base import GDBFaultInjector
    from ..simulators.base import Simulator
    from ..pyrenode_faults.base import PyRenodeFaultInjector


def load_experiment(path: str | Path) -> Experiment:
    config_path = Path(path).expanduser().resolve(strict=True)
    with config_path.open("rb") as config_file:
        config = tomllib.load(config_file)

    experiment_config = _table(config, "experiment")
    program_config = _table(config, "program")
    simulator_config = _table(config, "simulator")
    fault_config = _table(config, "fault")
    execution_config = _table(config, "execution")

    program_name = _required(program_config, "name", str)
    program = TestProgram(
        source=f"{program_name}.S",
        elf=_required(program_config, "elf", str),
    )

    simulator_name = _required(simulator_config, "name", str)
    unsupported_options = simulator_config.keys() - {
        "name",
        "timeout",
        "host",
        "port",
        "platform",
    }
    if unsupported_options:
        names = ", ".join(sorted(unsupported_options))
        raise ValueError(f"unsupported simulator configuration values: {names}")
    simulator_options = {
        key: value
        for key, value in simulator_config.items()
        if key in {"timeout", "host", "port"}
    }
    timeout = simulator_options.get("timeout", SimulatorConfig.timeout)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("simulator timeout must be a positive number")
    if "platform" in simulator_config:
        if simulator_name != "renode":
            raise ValueError("simulator platform is only supported for Renode")
        platform = _required(simulator_config, "platform", str)
        platform_path = Path(platform).expanduser()
        if not platform_path.is_absolute():
            platform_path = config_path.parent / platform_path
        simulator_options["platform"] = platform_path.resolve(strict=True)
    simulator = SimulatorFactory.create(
        simulator_name,
        SimulatorConfig(**simulator_options),
    )

    execution_mode = _execution_mode(execution_config)
    fault_injector = _fault_injector(
        fault_config,
        pyrenode=execution_mode == "pyrenode",
        program=program,
    )
    return Experiment(
        simulator=simulator,
        program=program,
        fault_injector=fault_injector,
        output_register=_required(execution_config, "output_register", str),
        step_after_injection=_boolean(execution_config, "step_after_injection", False),
        injection_address=_optional_address(
            execution_config, "inject_at", program
        ),
        end_address=_optional_address(execution_config, "end_at", program),
        name=_required(experiment_config, "name", str),
        execution_backend=_execution_backend(execution_config, simulator),
    )


def _execution_backend(
    config: dict[str, Any],
    simulator: Simulator,
) -> ExecutionBackend:
    return ExecutionBackendFactory.create(_execution_mode(config), simulator)


def _execution_mode(config: dict[str, Any]) -> str:
    configured_mode = config.get("mode")
    configured_backend = config.get("backend")
    if (
        configured_mode is not None
        and configured_backend is not None
        and configured_mode != configured_backend
    ):
        raise ValueError("execution mode and backend configuration must match")
    if configured_mode is not None:
        mode = configured_mode
    elif configured_backend is not None:
        mode = configured_backend
    else:
        mode = "gdb"
    if not isinstance(mode, str):
        raise ValueError("execution mode must be a string")
    return mode


def _fault_injector(
    config: dict[str, Any],
    *,
    pyrenode: bool = False,
    program: TestProgram,
) -> GDBFaultInjector | PyRenodeFaultInjector:
    fault_type = _required(config, "type", str)
    raw_value = _required(config, "value", (int, str))
    if fault_type == "pc":
        value = program.resolve_location(raw_value)
    else:
        value = _parse_integer(raw_value, "fault.value")

    if fault_type == "register":
        injector = PyRenodeRegisterFaultInjector if pyrenode else RegisterFaultInjector
        return injector(
            register=_required(config, "register", str),
            value=value,
        )
    if fault_type == "memory":
        injector = PyRenodeMemoryFaultInjector if pyrenode else MemoryFaultInjector
        return injector(
            address=_required(config, "address_register", str),
            value=value,
        )
    if fault_type == "pc":
        injector = PyRenodePcFaultInjector if pyrenode else PcFaultInjector
        return injector(value=value)

    raise ValueError(f"unsupported fault type: {fault_type!r}")


def _table(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"configuration section [{name}] is required")
    return value


def _required(
    config: dict[str, Any],
    name: str,
    expected_type: type | tuple[type, ...],
) -> Any:
    value = config.get(name)
    if not isinstance(value, expected_type):
        raise ValueError(f"configuration value {name!r} is missing or invalid")
    return value


def _optional_address(
    config: dict[str, Any],
    name: str,
    program: TestProgram,
) -> int | None:
    value = config.get(name)
    if value is None:
        return None
    if not isinstance(value, (int, str)):
        raise ValueError(f"configuration value {name!r} must be an address or symbol")
    return program.resolve_location(value)


def _boolean(config: dict[str, Any], name: str, default: bool) -> bool:
    value = config.get(name, default)
    if not isinstance(value, bool):
        raise ValueError(f"configuration value {name!r} must be a boolean")
    return value


def _parse_integer(value: int | str, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"configuration value {name!r} must be an integer")
    try:
        return int(value, 0) if isinstance(value, str) else value
    except ValueError as error:
        raise ValueError(
            f"configuration value {name!r} must be an integer"
        ) from error
