import argparse, os
from pathlib import Path
from m5.objects import PcCountTrackerManager
from m5.params import PcCountPair

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.memory.single_channel import SingleChannelDDR3_1600
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.exit_event import ExitEvent
from gem5.simulate.simulator import Simulator

p = argparse.ArgumentParser()
p.add_argument("--elf", required=True)
p.add_argument("--stop-pc", type=lambda x: int(x, 0), required=True)
p.add_argument("--save-to", required=True)          # checkpoint dir written at stop
p.add_argument("--restore-from", default=None)      # checkpoint dir to start from
p.add_argument("--max-ticks", type=int, default=10**10)  # hang detection
args = p.parse_args()

# The board MUST be identical for create and restore.
board = SimpleBoard(
    clk_freq="1GHz",
    processor=SimpleProcessor(cpu_type=CPUTypes.ATOMIC, isa=ISA.RISCV, num_cores=1),
    memory=SingleChannelDDR3_1600(size="256MiB"),
    cache_hierarchy=NoCache(),
)

# The checkpoint is now given to the workload, not to the Simulator.
if args.restore_from:
    board.set_se_binary_workload(
        BinaryResource(local_path=args.elf),
        checkpoint=Path(args.restore_from),
    )
else:
    board.set_se_binary_workload(BinaryResource(local_path=args.elf))

# Fire an exit event when the instruction at stop_pc retires.
core = board.get_processor().get_cores()[0]
targets = [PcCountPair(args.stop_pc, 1)]
manager = PcCountTrackerManager(targets=targets)
core.add_pc_tracker_probe(targets, manager)


def on_stop():
    os.makedirs(os.path.dirname(os.path.abspath(args.save_to)), exist_ok=True)
    simulator.save_checkpoint(args.save_to)
    yield True  # end simulation


simulator = Simulator(
    board=board,
    on_exit_event={ExitEvent.SIMPOINT_BEGIN: on_stop()},
)
simulator.run(max_ticks=args.max_ticks)