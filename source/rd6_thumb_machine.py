"""Strict shared-state Thumb-2 subset interpreter for offline RD-6 checks.

Unlike the earlier per-function interpreters, one register file, NZCV flag
set, IT state, stack and byte memory persist across calls. Callee stack
frames, callee-saved registers and return addresses are therefore executed
rather than mocked. Only explicitly decoded code ranges execute. Unmapped,
misaligned or unpermitted accesses, unsupported instruction forms, and
conditions that read a flag no executed instruction defined raise
MachineFault.

This is not a Cortex-M emulator. It does not model cycles, pipelines,
exception entry, caches or peripherals beyond caller-supplied region hooks.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone import arm_const as A

U32 = 0xFFFFFFFF
SP, LR, PC = 13, 14, 15
REGISTER_NAMES = {**{f"r{i}": i for i in range(13)}, "sb": 9, "sl": 10,
                  "fp": 11, "ip": 12, "sp": SP, "lr": LR, "pc": PC}
EQ, NE, HS, LO, MI, PL, VS, VC, HI, LS, GE, LT, GT, LE, AL = (
    A.ARM_CC_EQ, A.ARM_CC_NE, A.ARM_CC_HS, A.ARM_CC_LO, A.ARM_CC_MI,
    A.ARM_CC_PL, A.ARM_CC_VS, A.ARM_CC_VC, A.ARM_CC_HI, A.ARM_CC_LS,
    A.ARM_CC_GE, A.ARM_CC_LT, A.ARM_CC_GT, A.ARM_CC_LE, A.ARM_CC_AL)
INVERSE = {EQ: NE, NE: EQ, HS: LO, LO: HS, MI: PL, PL: MI, VS: VC, VC: VS,
           HI: LS, LS: HI, GE: LT, LT: GE, GT: LE, LE: GT}
FLAGS_READ = {EQ: "z", NE: "z", HS: "c", LO: "c", MI: "n", PL: "n",
              VS: "v", VC: "v", HI: "cz", LS: "cz", GE: "nv", LT: "nv",
              GT: "znv", LE: "znv"}
SHIFTS = {A.ARM_SFT_LSL: "lsl", A.ARM_SFT_LSR: "lsr",
          A.ARM_SFT_ASR: "asr", A.ARM_SFT_ROR: "ror"}
SHIFT_INSTRUCTIONS = {A.ARM_INS_LSL: "lsl", A.ARM_INS_LSR: "lsr",
                      A.ARM_INS_ASR: "asr", A.ARM_INS_ROR: "ror"}
LOADS = {A.ARM_INS_LDR: 4, A.ARM_INS_LDRH: 2, A.ARM_INS_LDRB: 1}
STORES = {A.ARM_INS_STR: 4, A.ARM_INS_STRH: 2, A.ARM_INS_STRB: 1}


class MachineFault(AssertionError):
    """Interpreted code left the modeled subset or broke a stated rule."""


def signed(value: int) -> int:
    return value - (1 << 32) if value & 0x80000000 else value


def add_with_carry(x: int, y: int, carry: int) -> tuple[int, bool, bool]:
    unsigned_sum = x + y + carry
    result = unsigned_sum & U32
    return (result, result != unsigned_sum,
            signed(result) != signed(x) + signed(y) + carry)


def shift_c(value: int, kind: str, amount: int,
            carry_in: bool | None) -> tuple[int, bool | None]:
    """ARMv7-M Shift_C. Amount zero leaves the carry flag unchanged."""
    if amount == 0:
        return value, carry_in
    if kind == "lsl":
        if amount > 32:
            return 0, False
        return (value << amount) & U32, bool((value >> (32 - amount)) & 1)
    if kind == "lsr":
        if amount > 32:
            return 0, False
        return value >> amount, bool((value >> (amount - 1)) & 1)
    if kind == "asr":
        amount = min(amount, 32)
        return ((signed(value) >> amount) & U32,
                bool((signed(value) >> (amount - 1)) & 1))
    if kind == "ror":
        amount %= 32
        result = (((value >> amount) | (value << (32 - amount))) & U32
                  if amount else value)
        return result, bool(result >> 31)
    raise MachineFault(f"unsupported shift {kind}")


def immediate_carry(value: int, carry_in: bool | None) -> bool | None:
    """ThumbExpandImm_C carry for a decoded immediate value.

    Byte-pattern forms, which include every 16-bit-encoding immediate, leave
    carry unchanged. A nonzero value outside those forms has exactly one
    rotated encoding, whose carry-out is bit 31 of the value.
    """
    low = value & 0xFF
    if (value <= 0xFF or value == low * 0x00010001
            or value == ((value >> 8) & 0xFF) * 0x01000100
            or value == low * 0x01010101):
        return carry_in
    return bool(value >> 31)


@dataclass(frozen=True)
class Operand:
    kind: str                 # "reg", "imm" or "mem"
    reg: int = -1             # register index for "reg"
    imm: int = 0
    base: int = -1            # memory base register index
    index: int = -1           # memory index register index, -1 for none
    disp: int = 0
    shift: str | None = None  # "lsl"/"lsr"/"asr"/"ror", or "unsupported"
    amount: int = 0
    subtracted: bool = False


@dataclass(frozen=True)
class Decoded:
    address: int
    size: int
    ident: int
    cc: int
    update_flags: bool
    writeback: bool
    mnemonic: str
    op_str: str
    operands: tuple[Operand, ...]
    owner: str

    def text(self) -> str:
        return f"0x{self.address:08X}: {self.mnemonic} {self.op_str}".rstrip()


def convert(instruction, owner: str) -> Decoded:
    operands = []
    for item in instruction.operands:
        kind = item.shift.type
        shift = (None if kind == A.ARM_SFT_INVALID
                 else SHIFTS.get(kind, "unsupported"))
        if item.type == A.ARM_OP_REG:
            operands.append(Operand("reg", reg=REGISTER_NAMES[instruction.reg_name(item.reg)],
                                    shift=shift, amount=item.shift.value,
                                    subtracted=item.subtracted))
        elif item.type == A.ARM_OP_IMM:
            operands.append(Operand("imm", imm=item.imm, shift=shift,
                                    amount=item.shift.value))
        elif item.type == A.ARM_OP_MEM:
            memory = item.mem
            operands.append(Operand(
                "mem", base=REGISTER_NAMES[instruction.reg_name(memory.base)],
                index=(REGISTER_NAMES[instruction.reg_name(memory.index)]
                       if memory.index else -1),
                disp=memory.disp, shift=shift, amount=item.shift.value,
                subtracted=item.subtracted))
        else:
            operands.append(Operand("unsupported"))
    ident = instruction.id
    if ident == A.ARM_INS_HINT and instruction.mnemonic == "nop":
        ident = A.ARM_INS_NOP  # Capstone 5 reports NOP as a hint.
    return Decoded(instruction.address, instruction.size, ident,
                   instruction.cc, instruction.update_flags,
                   instruction.writeback, instruction.mnemonic,
                   instruction.op_str, tuple(operands), owner)


@dataclass
class Region:
    name: str
    start: int
    data: bytearray
    writable: bool = False
    read_hook: Callable[[int, int], int] | None = None
    write_hook: Callable[[int, int, int], None] | None = None

    @property
    def end(self) -> int:
        return self.start + len(self.data)


class Memory:
    """Byte memory made only of named regions; everything else is unmapped."""

    def __init__(self) -> None:
        self.regions: list[Region] = []
        self.allowed_writes: set[str] | None = None
        self.log: list[tuple[str, int, int, int, int, str]] | None = None

    def add(self, name: str, start: int, contents: int | bytes, *,
            writable: bool = False, read_hook=None, write_hook=None) -> Region:
        region = Region(name, start, bytearray(contents), writable,
                        read_hook, write_hook)
        for other in self.regions:
            if not (region.end <= other.start or other.end <= region.start):
                raise MachineFault(f"regions {name} and {other.name} overlap")
        self.regions.append(region)
        return region

    def region(self, address: int, size: int) -> Region:
        for region in self.regions:
            if region.start <= address and address + size <= region.end:
                return region
        raise MachineFault(f"unmapped access at 0x{address:08X} size {size}")

    def read(self, address: int, size: int, pc: int = 0) -> int:
        if address % size:
            raise MachineFault(f"misaligned {size}-byte read at 0x{address:08X} from 0x{pc:08X}")
        region = self.region(address, size)
        if region.read_hook is not None:
            value = region.read_hook(address, size) & ((1 << (8 * size)) - 1)
        else:
            offset = address - region.start
            value = int.from_bytes(region.data[offset:offset + size], "little")
        if self.log is not None:
            self.log.append(("read", pc, address, size, value, region.name))
        return value

    def write(self, address: int, size: int, value: int, pc: int = 0) -> None:
        if address % size:
            raise MachineFault(f"misaligned {size}-byte write at 0x{address:08X} from 0x{pc:08X}")
        region = self.region(address, size)
        allowed = (region.writable if self.allowed_writes is None
                   else region.name in self.allowed_writes)
        if not allowed:
            raise MachineFault(f"write to {region.name} at 0x{address:08X} "
                               f"from 0x{pc:08X} is not permitted")
        value &= (1 << (8 * size)) - 1
        if self.log is not None:
            self.log.append(("write", pc, address, size, value, region.name))
        if region.write_hook is not None:
            region.write_hook(address, size, value)
            return
        offset = address - region.start
        region.data[offset:offset + size] = value.to_bytes(size, "little")

    def peek(self, address: int, size: int = 4) -> int:
        """Harness-side read that bypasses hooks, logging and permissions."""
        region = self.region(address, size)
        offset = address - region.start
        return int.from_bytes(region.data[offset:offset + size], "little")

    def poke(self, address: int, value: int, size: int = 4) -> None:
        """Harness-side write for modeled stock code, never interpreted code."""
        region = self.region(address, size)
        offset = address - region.start
        region.data[offset:offset + size] = (
            value & ((1 << (8 * size)) - 1)).to_bytes(size, "little")


class Program:
    """Instructions decoded linearly per named range, so IT blocks decode in context."""

    def __init__(self) -> None:
        self.disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
        self.disassembler.detail = True
        self.instructions: dict[int, Decoded] = {}
        self.ranges: list[tuple[int, int, str]] = []

    def add(self, name: str, start: int, code: bytes) -> None:
        decoded = list(self.disassembler.disasm(code, start))
        if sum(item.size for item in decoded) != len(code):
            raise MachineFault(f"{name} does not decode to its full {len(code)} bytes")
        for item in decoded:
            if item.address in self.instructions:
                raise MachineFault(f"{name} overlaps decoded code at 0x{item.address:08X}")
            self.instructions[item.address] = convert(item, name)
        self.ranges.append((start, start + len(code), name))
        self.ranges.sort()

    def fetch(self, pc: int) -> Decoded:
        instruction = self.instructions.get(pc)
        if instruction is None:
            raise MachineFault(f"no decoded instruction at 0x{pc:08X}")
        return instruction


class Thumb:
    """Execute decoded Thumb instructions on one shared machine state."""

    def __init__(self, memory: Memory, program: Program) -> None:
        self.memory = memory
        self.program = program
        self.regs = [0] * 16
        self.n = self.z = self.c = self.v = None
        self.it: list[int] = []
        self.primask = 0  # exception admission is modeled by the test harness
        self.intercepts: dict[int, Callable[[Thumb], None]] = {}
        self.observers: dict[int, list[Callable[[Thumb], None]]] = {}
        self.stats: Counter = Counter()
        self.by_owner: Counter = Counter()
        self.lowest_sp = 0

    # -- state -------------------------------------------------------------
    def poison_flags(self) -> None:
        self.n = self.z = self.c = self.v = None

    def context(self) -> tuple:
        # PRIMASK is not exception-stacked: exception return restores registers,
        # APSR and IT state, while the interrupt mask remains processor state.
        return (list(self.regs), (self.n, self.z, self.c, self.v), list(self.it))

    def restore(self, context: tuple) -> None:
        regs, flags, it = context
        self.regs = list(regs)
        self.n, self.z, self.c, self.v = flags
        self.it = list(it)

    def reset_statistics(self) -> None:
        self.stats = Counter()
        self.by_owner = Counter()
        self.lowest_sp = self.regs[SP]

    def set_register(self, index: int, value: int) -> None:
        if index == PC:
            raise MachineFault("direct PC write is outside the modeled subset")
        self.regs[index] = value & U32
        if index == SP:
            if self.regs[SP] % 4:
                raise MachineFault("stack pointer lost word alignment")
            self.lowest_sp = min(self.lowest_sp, self.regs[SP])

    def plain(self, instruction: Decoded, operand: Operand) -> int:
        """Index of an unshifted, non-PC register operand."""
        if operand.kind != "reg" or operand.shift is not None or operand.reg == PC:
            raise MachineFault(f"expected plain register in {instruction.text()}")
        return operand.reg

    def value(self, instruction: Decoded, operand: Operand) -> tuple[int, bool | None]:
        """Value and shifter carry-out of an immediate or (shifted) register."""
        if operand.kind == "imm":
            value = operand.imm & U32
            return value, immediate_carry(value, self.c)
        if operand.kind != "reg" or operand.reg == PC:
            raise MachineFault(f"unsupported operand in {instruction.text()}")
        value = self.regs[operand.reg]
        if operand.shift is None:
            return value, self.c
        if operand.shift == "unsupported":
            raise MachineFault(f"unsupported operand shift in {instruction.text()}")
        return shift_c(value, operand.shift, operand.amount, self.c)

    def condition_passes(self, condition: int) -> bool:
        if condition == AL:
            return True
        for flag in FLAGS_READ[condition]:
            if getattr(self, flag) is None:
                raise MachineFault(f"condition reads undefined {flag.upper()} flag "
                                   f"at 0x{self.regs[PC]:08X}")
        n, z, c, v = self.n, self.z, self.c, self.v
        if condition == EQ:
            return z
        if condition == NE:
            return not z
        if condition == HS:
            return c
        if condition == LO:
            return not c
        if condition == MI:
            return n
        if condition == PL:
            return not n
        if condition == VS:
            return v
        if condition == VC:
            return not v
        if condition == HI:
            return c and not z
        if condition == LS:
            return not c or z
        if condition == GE:
            return n == v
        if condition == LT:
            return n != v
        if condition == GT:
            return not z and n == v
        return z or n != v

    def set_nz(self, result: int) -> None:
        self.n, self.z = bool(result >> 31), result == 0

    # -- execution ---------------------------------------------------------
    def run(self, entry: int, stops: set[int], max_steps: int,
            pause_after: int | None = None) -> tuple[str, int]:
        self.regs[PC] = entry
        return self.resume(stops, max_steps, pause_after)

    def resume(self, stops: set[int], max_steps: int,
               pause_after: int | None = None) -> tuple[str, int]:
        steps = 0
        observers = self.observers
        while True:
            pc = self.regs[PC]
            if pc in stops:
                if self.it:
                    raise MachineFault(f"stopped inside an IT block at 0x{pc:08X}")
                return "stop", steps
            if pause_after is not None and steps == pause_after:
                return "pause", steps
            if steps >= max_steps:
                raise MachineFault(f"instruction bound {max_steps} exceeded at 0x{pc:08X}")
            if pc in observers:
                for observer in observers[pc]:
                    observer(self)
            self.step()
            steps += 1

    def step(self) -> None:
        pc = self.regs[PC]
        instruction = self.program.fetch(pc)
        stats = self.stats
        stats["instructions"] += 1
        self.by_owner[instruction.owner] += 1
        following = pc + instruction.size
        if instruction.ident == A.ARM_INS_IT:
            if self.it:
                raise MachineFault(f"IT inside IT block at 0x{pc:08X}")
            pattern = instruction.mnemonic[2:]
            if not set(pattern) <= {"t", "e"} or len(pattern) > 3:
                raise MachineFault(f"unexpected IT form {instruction.mnemonic}")
            first = instruction.cc
            self.it = [first] + [first if letter == "t" else INVERSE[first]
                                 for letter in pattern]
            stats["it"] += 1
            self.regs[PC] = following
            return
        if self.it:
            condition = self.it.pop(0)
            if instruction.cc != condition:
                raise MachineFault(f"decoded condition disagrees with IT state at 0x{pc:08X}")
            inside_it = True
        else:
            condition = instruction.cc
            if condition != AL and instruction.ident != A.ARM_INS_B:
                raise MachineFault(f"conditional instruction outside IT at 0x{pc:08X}")
            inside_it = False
        if instruction.ident == A.ARM_INS_NOP:
            stats["nop"] += 1
        if not self.condition_passes(condition):
            stats["condition_failed"] += 1
            self.regs[PC] = following
            return
        target = self.execute(instruction, following)
        if target is None:
            self.regs[PC] = following
            return
        if inside_it and self.it:
            raise MachineFault(f"branch before the end of an IT block at 0x{pc:08X}")
        stats["taken_branches"] += 1
        self.regs[PC] = target

    def call_target(self, target: int, following: int) -> int:
        self.set_register(LR, following | 1)
        self.stats["calls"] += 1
        if self.regs[SP] % 8:
            self.stats["calls_with_sp_not_8_aligned"] += 1
        hook = self.intercepts.get(target)
        if hook is None:
            return target
        self.stats["intercepted_calls"] += 1
        hook(self)
        self.poison_flags()
        return self.regs[LR] & ~1

    def interwork(self, value: int, pc: int) -> int:
        if not value & 1:
            raise MachineFault(f"branch to ARM state 0x{value:08X} from 0x{pc:08X}")
        return value & ~1

    def address(self, instruction: Decoded, operand: Operand) -> int:
        if operand.kind != "mem" or instruction.writeback or operand.subtracted:
            raise MachineFault(f"unsupported addressing in {instruction.text()}")
        base = ((instruction.address + 4) & ~3 if operand.base == PC
                else self.regs[operand.base])
        if operand.index >= 0:
            if operand.index in (SP, PC) or operand.disp:
                raise MachineFault(f"unsupported index form in {instruction.text()}")
            offset = self.regs[operand.index]
            if operand.shift == "lsl":
                offset = (offset << operand.amount) & U32
            elif operand.shift is not None:
                raise MachineFault(f"unsupported index shift in {instruction.text()}")
        else:
            offset = operand.disp
            if offset < 0:
                raise MachineFault(f"negative displacement in {instruction.text()}")
        return (base + offset) & U32

    def execute(self, instruction: Decoded, following: int) -> int | None:
        ident = instruction.ident
        operands = instruction.operands
        pc = instruction.address
        flags = instruction.update_flags
        regs = self.regs
        if instruction.mnemonic == "mrs" and instruction.op_str.endswith(", primask"):
            self.set_register(self.plain(instruction, operands[0]), self.primask)
            return None
        if instruction.mnemonic == "msr" and instruction.op_str.startswith("primask, "):
            self.primask = regs[self.plain(instruction, operands[1])] & 1
            return None
        if instruction.mnemonic == "cpsid" and instruction.op_str == "i":
            self.primask = 1
            return None
        if ident in (A.ARM_INS_ADD, A.ARM_INS_SUB, A.ARM_INS_RSB):
            destination = self.plain(instruction, operands[0])
            if len(operands) == 2:
                left = regs[destination]
                right, _ = self.value(instruction, operands[1])
            elif len(operands) == 3:
                left = regs[self.plain(instruction, operands[1])]
                right, _ = self.value(instruction, operands[2])
            else:
                raise MachineFault(f"unsupported add/sub form in {instruction.text()}")
            if ident == A.ARM_INS_ADD:
                result, carry, overflow = add_with_carry(left, right, 0)
            elif ident == A.ARM_INS_SUB:
                result, carry, overflow = add_with_carry(left, ~right & U32, 1)
            else:  # RSB: the operand minus the register
                result, carry, overflow = add_with_carry(right, ~left & U32, 1)
            self.set_register(destination, result)
            if flags:
                self.set_nz(result)
                self.c, self.v = carry, overflow
            return None
        if ident in (A.ARM_INS_CMP, A.ARM_INS_CMN):
            left = regs[self.plain(instruction, operands[0])]
            right, _ = self.value(instruction, operands[1])
            if ident == A.ARM_INS_CMP:
                result, carry, overflow = add_with_carry(left, ~right & U32, 1)
            else:
                result, carry, overflow = add_with_carry(left, right, 0)
            self.set_nz(result)
            self.c, self.v = carry, overflow
            return None
        if ident in (A.ARM_INS_TST, A.ARM_INS_TEQ):
            left = regs[self.plain(instruction, operands[0])]
            right, carry = self.value(instruction, operands[1])
            result = left & right if ident == A.ARM_INS_TST else left ^ right
            self.set_nz(result)
            self.c = carry
            return None
        if ident in (A.ARM_INS_AND, A.ARM_INS_ORR, A.ARM_INS_EOR, A.ARM_INS_BIC):
            destination = self.plain(instruction, operands[0])
            if len(operands) == 2:
                left = regs[destination]
                right, carry = self.value(instruction, operands[1])
            elif len(operands) == 3:
                left = regs[self.plain(instruction, operands[1])]
                right, carry = self.value(instruction, operands[2])
            else:
                raise MachineFault(f"unsupported logical form in {instruction.text()}")
            if ident == A.ARM_INS_AND:
                result = left & right
            elif ident == A.ARM_INS_ORR:
                result = left | right
            elif ident == A.ARM_INS_EOR:
                result = left ^ right
            else:
                result = left & ~right & U32
            self.set_register(destination, result)
            if flags:
                self.set_nz(result)
                self.c = carry
            return None
        if ident in (A.ARM_INS_MOV, A.ARM_INS_MVN):
            if len(operands) != 2:
                raise MachineFault(f"unsupported move form in {instruction.text()}")
            destination = self.plain(instruction, operands[0])
            value, carry = self.value(instruction, operands[1])
            if ident == A.ARM_INS_MVN:
                value = ~value & U32
            self.set_register(destination, value)
            if flags:
                self.set_nz(value)
                self.c = carry
            return None
        if ident in (A.ARM_INS_MOVW, A.ARM_INS_MOVT):
            destination = self.plain(instruction, operands[0])
            value = operands[1].imm & 0xFFFF
            if ident == A.ARM_INS_MOVT:
                value = (regs[destination] & 0xFFFF) | (value << 16)
            self.set_register(destination, value)
            return None
        if ident in SHIFT_INSTRUCTIONS:
            destination = self.plain(instruction, operands[0])
            if len(operands) == 2:
                value = regs[destination]
                amount_operand = operands[1]
            elif len(operands) == 3:
                value = regs[self.plain(instruction, operands[1])]
                amount_operand = operands[2]
            else:
                raise MachineFault(f"unsupported shift form in {instruction.text()}")
            if amount_operand.kind == "imm":
                amount = amount_operand.imm
            else:
                amount = regs[self.plain(instruction, amount_operand)] & 0xFF
            result, carry = shift_c(value, SHIFT_INSTRUCTIONS[ident], amount, self.c)
            self.set_register(destination, result)
            if flags:
                self.set_nz(result)
                self.c = carry
            return None
        if ident in (A.ARM_INS_MUL, A.ARM_INS_MLA, A.ARM_INS_MLS, A.ARM_INS_UDIV):
            registers = [self.plain(instruction, item) for item in operands]
            if ident == A.ARM_INS_MUL and len(registers) == 3:
                result = regs[registers[1]] * regs[registers[2]]
            elif ident in (A.ARM_INS_MLA, A.ARM_INS_MLS) and len(registers) == 4:
                product = regs[registers[1]] * regs[registers[2]]
                addend = regs[registers[3]]
                result = addend + product if ident == A.ARM_INS_MLA else addend - product
            elif ident == A.ARM_INS_UDIV and len(registers) == 3:
                divisor = regs[registers[2]]
                if divisor == 0:
                    raise MachineFault(f"division by zero at 0x{pc:08X}")
                result = regs[registers[1]] // divisor
                self.stats["divides"] += 1
            else:
                raise MachineFault(f"unsupported multiply/divide form in {instruction.text()}")
            self.set_register(registers[0], result)
            if flags:
                if ident != A.ARM_INS_MUL:
                    raise MachineFault(f"unexpected flag-setting form in {instruction.text()}")
                self.set_nz(regs[registers[0]])
            return None
        if ident in (A.ARM_INS_UXTB, A.ARM_INS_UXTH, A.ARM_INS_CLZ):
            if len(operands) != 2:
                raise MachineFault(f"unsupported extend form in {instruction.text()}")
            destination = self.plain(instruction, operands[0])
            value = regs[self.plain(instruction, operands[1])]
            if ident == A.ARM_INS_UXTB:
                result = value & 0xFF
            elif ident == A.ARM_INS_UXTH:
                result = value & 0xFFFF
            else:
                result = 32 - value.bit_length()
            self.set_register(destination, result)
            return None
        if ident == A.ARM_INS_UBFX:
            destination = self.plain(instruction, operands[0])
            value = regs[self.plain(instruction, operands[1])]
            lsb, width = operands[2].imm, operands[3].imm
            self.set_register(destination, (value >> lsb) & ((1 << width) - 1))
            return None
        if ident == A.ARM_INS_BFI:
            if (len(operands) != 4 or operands[0].kind != "reg"
                    or operands[1].kind != "reg"
                    or any(item.kind != "imm" for item in operands[2:])
                    or operands[0].reg in (SP, PC) or operands[1].reg in (SP, PC)):
                raise MachineFault(f"unsupported BFI form in {instruction.text()}")
            destination, source = operands[0].reg, operands[1].reg
            lsb, width = operands[2].imm, operands[3].imm
            if not (0 <= lsb < 32 and 1 <= width <= 32 - lsb):
                raise MachineFault(f"invalid BFI field in {instruction.text()}")
            mask = ((1 << width) - 1) << lsb
            self.set_register(destination, (regs[destination] & ~mask) |
                              ((regs[source] << lsb) & mask))
            return None
        if ident == A.ARM_INS_TBB:
            if (len(operands) != 1 or operands[0].kind != "mem"
                    or operands[0].base != PC or operands[0].index in (-1, SP, PC)
                    or operands[0].disp or operands[0].shift is not None
                    or instruction.writeback or operands[0].subtracted):
                raise MachineFault(f"unsupported TBB form in {instruction.text()}")
            # ARMv7-M TBB uses the unaligned Thumb PC (instruction + 4),
            # unlike literal loads. Only the observed PC-relative form runs.
            branch_base = (pc + 4) & U32
            table = (branch_base + regs[operands[0].index]) & U32
            offset = self.memory.read(table, 1, pc)
            self.stats["loads"] += 1
            return (branch_base + 2 * offset) & U32
        if ident in LOADS or ident in STORES:
            size = LOADS.get(ident) or STORES[ident]
            register = self.plain(instruction, operands[0])
            if instruction.writeback:
                if (ident != A.ARM_INS_LDRB or len(operands) != 3
                        or operands[1].kind != "mem" or operands[1].disp
                        or operands[1].index != -1 or operands[1].subtracted
                        or operands[1].base in (SP, PC, register)
                        or operands[2].kind != "imm" or operands[2].imm != 1):
                    raise MachineFault(f"unsupported post-index load in {instruction.text()}")
                base = operands[1].base
                address = regs[base]
                self.set_register(register, self.memory.read(address, 1, pc))
                self.set_register(base, address + 1)
                self.stats["loads"] += 1
                return None
            address = self.address(instruction, operands[1])
            if ident in LOADS:
                self.stats["loads"] += 1
                self.set_register(register, self.memory.read(address, size, pc))
            else:
                self.stats["stores"] += 1
                self.memory.write(address, size, regs[register], pc)
            return None
        if ident in (A.ARM_INS_LDRD, A.ARM_INS_STRD):
            first = self.plain(instruction, operands[0])
            second = self.plain(instruction, operands[1])
            address = self.address(instruction, operands[2])
            if ident == A.ARM_INS_LDRD:
                self.stats["loads"] += 2
                low = self.memory.read(address, 4, pc)
                high = self.memory.read(address + 4, 4, pc)
                self.set_register(first, low)
                self.set_register(second, high)
            else:
                self.stats["stores"] += 2
                self.memory.write(address, 4, regs[first], pc)
                self.memory.write(address + 4, 4, regs[second], pc)
            return None
        if ident in (A.ARM_INS_PUSH, A.ARM_INS_POP):
            registers = [item.reg for item in operands]
            if registers != sorted(set(registers)) or SP in registers:
                raise MachineFault(f"unexpected register list in {instruction.text()}")
            base = regs[SP]
            if ident == A.ARM_INS_PUSH:
                if PC in registers:
                    raise MachineFault(f"push of PC in {instruction.text()}")
                base -= 4 * len(registers)
                for slot, register in enumerate(registers):
                    self.memory.write(base + 4 * slot, 4, regs[register], pc)
                self.stats["stores"] += len(registers)
                self.set_register(SP, base)
                return None
            target = None
            for slot, register in enumerate(registers):
                value = self.memory.read(base + 4 * slot, 4, pc)
                if register == PC:
                    target = self.interwork(value, pc)
                else:
                    self.set_register(register, value)
            self.stats["loads"] += len(registers)
            self.set_register(SP, base + 4 * len(registers))
            return target
        if ident == A.ARM_INS_B:
            return operands[0].imm
        if ident in (A.ARM_INS_CBZ, A.ARM_INS_CBNZ):
            value = regs[self.plain(instruction, operands[0])]
            if (value == 0) == (ident == A.ARM_INS_CBZ):
                return operands[1].imm
            return None
        if ident == A.ARM_INS_BL:
            return self.call_target(operands[0].imm, following)
        if ident == A.ARM_INS_BLX:
            if operands[0].kind != "reg":
                raise MachineFault(f"BLX immediate changes state in {instruction.text()}")
            value = regs[self.plain(instruction, operands[0])]
            return self.call_target(self.interwork(value, pc), following)
        if ident == A.ARM_INS_BX:
            if operands[0].kind != "reg" or operands[0].reg == PC:
                raise MachineFault(f"unsupported BX form in {instruction.text()}")
            return self.interwork(regs[operands[0].reg], pc)
        if ident == A.ARM_INS_ADR:
            if len(operands) != 2 or operands[1].kind != "imm":
                raise MachineFault(f"unsupported ADR form in {instruction.text()}")
            destination = self.plain(instruction, operands[0])
            self.set_register(destination, (((pc + 4) & ~3) + operands[1].imm) & U32)
            return None
        if ident == A.ARM_INS_NOP:
            return None
        raise MachineFault(f"unsupported instruction {instruction.text()}")
