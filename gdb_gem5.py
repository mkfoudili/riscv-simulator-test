import argparse

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.memory.single_channel import SingleChannelDDR3_1600
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

parser = argparse.ArgumentParser()
parser.add_argument("--elf", required=True)
args = parser.parse_args()

board = SimpleBoard(
    clk_freq="1GHz",
    processor=SimpleProcessor(cpu_type=CPUTypes.ATOMIC, isa=ISA.RISCV, num_cores=1),
    memory=SingleChannelDDR3_1600(size="256MiB"),
    cache_hierarchy=NoCache(),
)
board.set_se_binary_workload(BinaryResource(local_path=args.elf))

board.workload.wait_for_remote_gdb = True

Simulator(board=board).run()
