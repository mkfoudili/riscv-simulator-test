from .gem5 import Gem5Simulator
from .qemu import QemuSimulator
from .renode import RenodeSimulator


class SimulatorFactory:

    @staticmethod
    def create(name, config):
        if name == "qemu":
            return QemuSimulator(config)

        if name == "gem5":
            return Gem5Simulator(config)

        if name == "renode":
            return RenodeSimulator(config)

        raise ValueError(f"Unsupported simulator: {name}")