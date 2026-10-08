from collections.abc import Sequence
import argparse
from pathlib import Path
from time import perf_counter

from src.fi.config.experiment import load_experiment


def main(argv: Sequence[str] | None = None) -> None:
    start_time = perf_counter()
    parser = argparse.ArgumentParser(description="Run a configured RISC-V experiment.")
    parser.add_argument("config", type=Path, help="path to an experiment TOML file")
    config_path = parser.parse_args(argv).config

    experiment = load_experiment(config_path)
    result = experiment.run()

    elapsed_time = perf_counter() - start_time
    print(f"{experiment.name}: {result}")
    print(f"Execution time: {elapsed_time:.3f} seconds")


if __name__ == "__main__":
    main()
