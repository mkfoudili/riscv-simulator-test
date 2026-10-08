import os


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GEM5 = "/home/khadidja/gem5/build/RISCV/gem5.opt"


class Workspace:
    def __init__(self, root=HERE, gem5=None, checkpoint_script=None):
        self.root = os.path.abspath(root)
        self.gem5 = gem5 or os.environ.get("GEM5_BIN", DEFAULT_GEM5)
        self._checkpoint_script = checkpoint_script

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def elf_path(self, elf):
        return self.path(elf)

    def experiment_path(self, elf):
        return self.path(f"fi_{os.path.basename(os.fspath(elf))}")

    @property
    def checkpoint_script(self):
        if self._checkpoint_script is not None:
            return os.fspath(self._checkpoint_script)
        return self.path("gem5_ckpt.py")
