from dataclasses import dataclass
from pathlib import Path


@dataclass
class SimulatorConfig:
    timeout: float = 5.0
    host: str = "localhost"
    port: int = 1234
    platform: Path | None = None