import glob
import gzip
import os
import re

from elftools.elf.elffile import ELFFile

from .workspace import Workspace


THREAD_CONTEXT_SECTION = r"\.xc\.0\]$"


class CheckpointState:
    REG_BYTES = 8

    def __init__(self, elf, workspace=None):
        self.elf = elf
        self.workspace = workspace or Workspace()

    @staticmethod
    def _cpt(directory):
        return os.path.join(directory, "m5.cpt")

    def _load(self, directory):
        with open(self._cpt(directory)) as checkpoint:
            return checkpoint.read().split("\n")

    def _save(self, directory, lines):
        with open(self._cpt(directory), "w") as checkpoint:
            checkpoint.write("\n".join(lines))

    @staticmethod
    def _section(lines, pattern):
        start = next(i for i, line in enumerate(lines)
                     if line.startswith("[") and re.search(pattern, line))
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].startswith("[")), len(lines))
        return start, end

    def _get_key(self, lines, section, key):
        start, end = self._section(lines, section)
        for i in range(start + 1, end):
            if lines[i].startswith(key + "="):
                return lines[i].split("=", 1)[1]
        raise KeyError(key)

    def _set_key(self, lines, section, key, value):
        start, end = self._section(lines, section)
        for i in range(start + 1, end):
            if lines[i].startswith(key + "="):
                lines[i] = f"{key}={value}"
                return
        raise KeyError(key)

    def read_reg(self, directory, number):
        tokens = self._get_key(
            self._load(directory), THREAD_CONTEXT_SECTION, "regs.integer"
        ).split()
        if len(tokens) <= 32:
            return int(tokens[number])
        start = number * self.REG_BYTES
        data = bytes(int(token) for token in tokens[start:start + self.REG_BYTES])
        return int.from_bytes(data, "little")

    def write_reg(self, directory, number, value):
        lines = self._load(directory)
        tokens = self._get_key(
            lines, THREAD_CONTEXT_SECTION, "regs.integer"
        ).split()
        if len(tokens) <= 32:
            tokens[number] = str(value)
        else:
            start = number * self.REG_BYTES
            mask = 2 ** (8 * self.REG_BYTES) - 1
            data = (value & mask).to_bytes(self.REG_BYTES, "little")
            tokens[start:start + self.REG_BYTES] = [str(byte) for byte in data]
        self._set_key(
            lines, THREAD_CONTEXT_SECTION, "regs.integer", " ".join(tokens)
        )
        self._save(directory, lines)

    def write_pc(self, directory, pc):
        lines = self._load(directory)
        self._set_key(lines, THREAD_CONTEXT_SECTION, "_pc", pc)
        self._set_key(lines, THREAD_CONTEXT_SECTION, "_npc", pc + 4)
        self._save(directory, lines)

    def write_mem(self, directory, vaddr, data: bytes):
        pmem_path = glob.glob(os.path.join(directory, "*.pmem"))[0]
        with gzip.open(pmem_path, "rb") as memory_file:
            pmem = bytearray(memory_file.read())
        offset = self._vaddr_to_offset(pmem, vaddr)
        pmem[offset:offset + len(data)] = data
        with gzip.open(pmem_path, "wb") as memory_file:
            memory_file.write(pmem)

    def _vaddr_to_offset(self, pmem, vaddr):
        """Locate an SE-mode virtual address inside the physical memory image."""
        with open(self.workspace.elf_path(self.elf), "rb") as elf_file:
            for segment in ELFFile(elf_file).iter_segments():
                if segment["p_type"] != "PT_LOAD":
                    continue
                lo = segment["p_vaddr"]
                hi = lo + segment["p_memsz"]
                if lo <= vaddr < hi:
                    index = pmem.find(segment.data()[:64])
                    if index < 0:
                        raise RuntimeError("segment not found in pmem")
                    return index + (vaddr - lo)
        raise RuntimeError(f"{vaddr:#x} not in any PT_LOAD segment")
