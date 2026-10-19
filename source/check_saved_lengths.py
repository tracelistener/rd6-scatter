"""Offline checks for Scatter v1.4's saved lengths (source/saved_lengths.py), on the MIDI extra-hit build.

The actual bytes run in source/rd6_thumb_machine.py against a model of the RD-6's 32 KB
I2C EEPROM: the two stock EEPROM routines (read 0x0800381C, write 0x0800383A) are replaced
by stubs that read or write the model, so every caller, stock or new, sees the same
EEPROM. Writes wrap inside a 64-byte page, as on the part. No decoded firmware is saved
and no hardware is used.

1. Bytes: the build differs from the MIDI extra-hit build only at the five listed sites
   and in the five new routines; the MIDI routines and v1.3's routines are unchanged
   apart from set_length's store; every branch matches the listing; the mask stays
   recoverable.
2. Stock EEPROM audit (1.0.5): only the two routines drive the I2C code, every call of
   them is in the documented list, and the stock pattern load, read, save, playing-pattern
   save, tidy-up save and factory reset, run on the model, touch only the first 22 bytes
   of a slot.
3. Start-up: all 32 records read once, valid ones cached and the rest treated as no
   saved lengths (wrong tag, a length over 16, wrong check, blank or random bytes), and
   the loaded pattern given its lengths.
4. Pattern loads: the stock load routine (0x08003630) does exactly what it does in the
   MIDI build, plus the new pattern's lengths in LEN once the cache is ready.
5. Buttons: every v1.3 gesture still works; setting a length also stores it for the
   playing pattern and marks that slot; the Pattern Play buttons in 3,000 random cases
   match the MIDI build apart from that.
6. Saving: with nothing marked the main loop's save matches the MIDI build; marked slots
   are written one per save as tag, lengths and check, after the slot's pattern, and read
   back; a write that doesn't stick is retried at the next 3 saves, then dropped.
7. Round trips: lengths set on random patterns, patterns changed, saves, then a power
   cycle: every pattern gets its lengths back, and no pattern byte changes.
8. Pattern Write's lights: the light builder in random states of every mode, playing or not,
   matches the MIDI build, except with a voice of its own length selected in Pattern Write
   while playing: its steps up to its length, the running light on the step it last played.
"""
from pathlib import Path
import hashlib, json, random, sys
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'source')); sys.path.insert(0, str(HERE / 'scripts'))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from apply_patch import apply
from build_scatter_v1_2 import longest_run
from build_scatter_v1_3 import decode, MIN_RUN
from build_saved_lengths import build, OUT, MIDI
from rd6_thumb_machine import Program, Memory, Thumb
from midi_firmware_audit import graph, reach, word
import check_scatter_v1_3 as C
import midi_extra as X
import saved_lengths as L
import mute_roll as V

BASE, STOP, SP = 0x08002800, C.STOP_LR, C.SP_TOP
LOAD_PATTERN, LOAD_TAIL = 0x08003630, 0x08006E68     # stock load of the playing pattern and its tail call
SAVER, SAVER_TAIL = 0x080072E4, 0x08002A5C           # the main loop's save and its tail call
SAVE_REQUEST = 0x20000210                            # set by a timer about every half second
PLAYING_PATTERN = 0x20000A9C
I2C_READ, I2C_WRITE = 0x08003E68, 0x080040F4
DELAY_MS = 0x08003186                                # busy-wait, after each EEPROM write and in the save loops
STUBS = (L.EEPROM_READ, L.EEPROM_WRITE, DELAY_MS, LOAD_TAIL, SAVER_TAIL, L.LAST_INIT)
LEN_AT = V.ST + V.LEN + 1                            # LEN[1..8], BD..CH
STATE = set(range(V.ST + L.LOADED - 0x20000000, V.ST + L.END - 0x20000000))
SLOTS = [s * 64 for s in range(32)]
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
md.detail = True

# Every call of the stock EEPROM routines in 1.0.5, from the vectors and the main loop.
# Pattern slots (0x0000-0x07FF) are only ever read or written as 22 bytes at the slot, or
# one byte at a time inside those 22 (the read-back loops).
STOCK_SITES = {
    0x0800315E: 'write 22 bytes at slot i: factory reset of the 32 patterns',
    0x080031F2: 'write 1 byte at song block + 0xFA',
    0x0800360E: 'write 22 bytes of the playing pattern at its slot (after tidy-up)',
    0x08003664: 'read 22 bytes of a slot into the playing pattern',
    0x0800369E: 'read 22 bytes of a slot into the SysEx buffer',
    0x080036BA: 'read 0xFD bytes of a song block',
    0x08003726: 'write 22 bytes at slot (SysEx pattern restore)',
    0x08003730: 'read back those 22 bytes',
    0x08003748: 'rewrite 1 byte of those 22',
    0x08003780: 'read a song block',
    0x0800379C: 'rewrite 1 byte of a song block',
    0x080037E0: 'write 22 bytes of the playing pattern at its slot',
    0x080037EA: 'read back those 22 bytes',
    0x08003800: 'rewrite 1 byte of those 22',
    0x08004360: 'write 1 byte at song block + 0xFA',
    0x08004400: 'write 1 byte at 0x3081 (setting)',
    0x08005B48: 'write 22 bytes of the playing pattern at its slot',
    0x08005C48: 'write 1 byte at song block + 0xFB',
    0x08005EDE: 'write 1 byte at 0x3000',
    0x080061CC: 'write 1 byte at 0x3087 (marker)',
    0x080061DC: 'write 1 byte at 0x3087 (marker)',
    0x08006FE2: 'write 1 byte at 0x3086 (setting)',
    0x08006FFC: 'write 1 byte at 0x3085 (setting)',
    0x080079C2: 'write 1 byte in a song block',
    0x080079F8: 'write 1 byte at song block + 0xFA',
    0x08007C3A: 'write a song block, page by page',
    0x08007C5A: 'write a song block, page by page',
    0x08007C6A: 'write a song block, page by page',
    0x08007C92: 'write a song block, page by page',
    0x080084FA: 'write 1 byte at 0x3083 (SysEx setting)',
    0x08008602: 'write 1 byte at 0x3082 (SysEx setting)',
    0x0800862E: 'write 1 byte at 0x3081 (SysEx setting)',
    0x080086BE: 'write 1 byte at 0x3086 (SysEx setting)',
    0x08008702: 'write 1 byte at 0x3084 (SysEx setting)',
    0x08008AD8: 'write 9 bytes at 0x3080 (default settings)',
}


def record(lengths):
    body = bytes([L.TAG, *lengths])
    return body + bytes([~sum(body) & 0xFF])


def lengths_of(rec):
    """The lengths a 10-byte record holds, or None if it isn't a valid record."""
    if rec[0] != L.TAG or any(x > 16 for x in rec[1:9]) or rec[9] != ~sum(rec[:9]) & 0xFF: return None
    return list(rec[1:9])


class EEPROM:
    def __init__(self, data=None):
        self.data = bytearray(data if data is not None else b'\xff' * 0x8000)
        self.ops, self.drop = [], None

    def read(self, vm, memory):
        address, buffer, n = vm.regs[0] & 0xFFFF, vm.regs[1], vm.regs[2]
        if address + n > 0x8000: n = 0x8000 - address        # as the stock routine clamps it
        for i in range(n): memory.poke(buffer + i, self.data[address + i], 1)
        self.ops.append(('read', address, n))

    def write(self, vm, memory):
        address, buffer, n = vm.regs[0] & 0xFFFF, vm.regs[1], vm.regs[2]
        data = bytes(memory.peek(buffer + i, 1) for i in range(n))
        self.ops.append(('write', address, n, data))
        if self.drop and self.drop(address, n): return
        for i, b in enumerate(data):                          # a page write wraps inside its page
            self.data[(address & ~63) | ((address + i) & 63)] = b


def collect(image, roots, exclude):
    """Instruction addresses of every function reachable from roots, minus exclude."""
    g = graph(image, roots)
    keep, todo = set(), list(roots)
    while todo:
        f = todo.pop()
        if f in keep or f in exclude: continue
        keep.add(f)
        assert not g[f][3], f'indirect control flow in {f:#x}'
        todo += [c for c in g[f][1] | g[f][2] if c not in exclude]
    return set().union(*(g[f][0] for f in keep))


def code_of(name, module):
    """(start, end) of a routine's instructions."""
    source = module.listing(name, module.ADDRESS['APPLY'] if module is L else module.ADDRESS['SAFE'])
    instrs, _ = module.parse(source)
    last = list(md.disasm(module.BODY[name], module.ADDRESS[name], len(instrs)))[-1]
    return module.ADDRESS[name], last.address + last.size


class Rig:
    """The image's code reachable from roots, plus extra ranges, on 16 KB of RAM, with the
    EEPROM routines (and the routines in STUBS) replaced by returning stubs."""
    def __init__(self, image, roots=(), extra=(), eeprom=None, ports=False):
        addresses = collect(image, list(roots), set(STUBS)) if roots else set()
        # Callers that branch (not call) into the EEPROM routines take their code, and the I2C
        # code behind it, as their own; all of that is behind the stubs.
        addresses -= collect(image, [L.EEPROM_READ, L.EEPROM_WRITE, DELAY_MS], set())
        for a, b in extra:
            addresses |= {i.address for i in md.disasm(image[a - BASE:b - BASE], a)}
        program, run_start, run_end = Program(), None, None
        for at in sorted(addresses):
            size = next(md.disasm(image[at - BASE:at - BASE + 4], at, 1)).size
            if run_start is not None and at == run_end: run_end += size; continue
            if run_start is not None: program.add(hex(run_start), run_start, image[run_start - BASE:run_end - BASE])
            run_start, run_end = at, at + size
        if run_start is not None: program.add(hex(run_start), run_start, image[run_start - BASE:run_end - BASE])
        for stub in STUBS: program.add(f'stub {stub:#x}', stub, bytes.fromhex('7047'))   # bx lr
        self.memory = Memory()
        self.memory.add('flash', BASE, image)
        self.ram = self.memory.add('ram', 0x20000000, 16384, writable=True)
        if ports:
            self.c, self.b = C.Port('GPIOC', 0x48000800), C.Port('GPIOB', 0x48000400)
            for port in (self.b, self.c):
                self.memory.add(port.name, port.base, 0x30, writable=True, read_hook=port.read, write_hook=port.write)
        self.vm = Thumb(self.memory, program)
        self.eeprom = eeprom or EEPROM()
        self.stubbed = []
        self.vm.observers[L.EEPROM_READ] = [lambda vm: self.eeprom.read(vm, self.memory)]
        self.vm.observers[L.EEPROM_WRITE] = [lambda vm: self.eeprom.write(vm, self.memory)]
        for stub in (LOAD_TAIL, SAVER_TAIL, L.LAST_INIT):
            self.vm.observers[stub] = [lambda vm, s=stub: self.stubbed.append(s)]

    def poke(self, address, value, size=4): self.memory.poke(address, value, size)
    def peek(self, address, size=4): return self.memory.peek(address, size)
    def st(self, offset, size=1): return self.peek(V.ST + offset, size)
    def set_st(self, offset, value, size=1): self.poke(V.ST + offset, value, size)
    def lens(self): return [self.peek(LEN_AT + i, 1) for i in range(8)]
    def cache(self, slot): return [self.st(L.CACHE + 8 * slot + i) for i in range(8)]

    def run(self, entry, stops=(), max_steps=200000, **regs):
        vm = self.vm
        for name, value in regs.items(): vm.regs[int(name[1:])] = value
        vm.regs[13], vm.regs[14] = SP, STOP | 1
        status, _ = vm.run(entry, set(stops) | {STOP}, max_steps)
        assert status == 'stop', status
        assert not vm.primask and (vm.regs[15] != STOP or vm.regs[13] == SP)
        return vm.regs[15]


def new_ranges():
    return [code_of(name, L) for name in L.ORDER]


# ---------------------------------------------------------------- bytes and the stock audit

def check_bytes(midi, image):
    allowed = set()
    for name, site, old, new in L.sites():
        assert midi[site - BASE:site - BASE + 4] == old and image[site - BASE:site - BASE + 4] == new, name
        allowed |= set(range(site, site + 4))
    for name in L.ORDER:
        at, body = L.ADDRESS[name], L.BODY[name]
        V.SOURCE['LEN_' + name] = L.listing(name, L.ADDRESS['APPLY'])
        assert image[at - BASE:at - BASE + len(body)] == body and not V.check_branches('LEN_' + name, at, body), name
        allowed |= set(range(at, at + len(body)))
    changed = {BASE + i for i, (a, b) in enumerate(zip(midi, image)) if a != b}
    assert changed <= allowed, sorted(hex(a) for a in changed - allowed)[:8]
    for module, names in ((V, V.ORDER), (X, X.ORDER)):
        for name in names:
            at, body = module.ADDRESS[name], module.BODY[name]
            now = bytearray(image[at - BASE:at - BASE + len(body)])
            if module is V and name == 'PANEL':
                i = L.SET_LENGTH_STORE - at
                now[i:i + 4] = bytes.fromhex('80f82c10')
            if module is V and name == 'TICK':
                i = X.MID_SITE - at
                now[i:i + 4] = bytes.fromhex('15202860')
            assert bytes(now) == body or (module is V and name == 'TICK' and image[at - BASE:at - BASE + len(body)] == midi[at - BASE:at - BASE + len(body)]), name
    run = longest_run(image)
    assert run >= MIN_RUN
    return len(changed), run


def audit(stock):
    """Who drives the EEPROM in stock 1.0.5, and which bytes the pattern paths touch."""
    vec = {i: word(stock, BASE + 4 * i) for i in range(1, 84)}
    roots = sorted({v & ~1 for v in vec.values() if v not in (0, 0x08002AAB)}) + [0x080093AC]
    g = graph(stock, roots)
    sites, drivers = set(), set()
    for f, info in g.items():
        for a in info[0]:
            ins = next(md.disasm(stock[a - BASE:a - BASE + 4], a, 1))
            if ins.mnemonic in ('bl', 'b.w', 'b') and ins.operands:
                t = ins.operands[0].imm
                if t in (L.EEPROM_READ, L.EEPROM_WRITE): sites.add(a)
                if t in (I2C_READ, I2C_WRITE): drivers.add(a)
    # The I2C code is entered only from inside the two EEPROM routines (0x0800381C-0x08003853).
    assert drivers and all(0x0800381C <= a < 0x08003854 for a in drivers), sorted(map(hex, drivers))
    assert sites == set(STOCK_SITES), sorted(hex(s) for s in sites ^ set(STOCK_SITES))
    # The pattern paths on the model: a sentinel in bytes 22-63 of every slot survives.
    sentinel = bytearray(random.Random(7).randbytes(0x8000))
    for s in SLOTS:
        rec = sentinel[s:s + 22]
        rec[1] %= 4; rec[2] = rec[2] % 16 + 1                # a tidy pattern header
        sentinel[s:s + 22] = rec
    runs = 0
    for entry, regs, setup in (
            (0x0800368C, dict(r0=1, r1=7), None),                                  # SysEx read of g2 p8
            (0x08003704, dict(r0=0, r1=3), None),                                  # SysEx restore of g1 p4
            (0x080037C0, dict(r0=PLAYING_PATTERN), lambda r: (r.poke(0x200009C0, 5), r.poke(0x20000224, 1, 1))),
            (0x080035EC, {}, lambda r: (r.poke(0x200009C0, 9), r.poke(0x20000224, 0, 1))),
            (0x0800314C, {}, None),                                                # factory reset
            (LOAD_PATTERN, {}, lambda r: (r.poke(0x200009C0, 2), r.poke(0x200009CC, 1, 1), r.poke(0x20000260, 2, 1),
                                          r.poke(SLOT_SENTINEL, 0xFFFF, 2)))):
        rig = Rig(stock, [entry], eeprom=EEPROM(sentinel))
        if setup: setup(rig)
        for i in range(22): rig.poke(PLAYING_PATTERN + i, (i * 37 + 5) & 0xFF, 1)
        rig.poke(PLAYING_PATTERN + 1, 2, 1); rig.poke(PLAYING_PATTERN + 2, 12, 1)
        rig.run(entry, {LOAD_TAIL}, **regs)
        touched = [op for op in rig.eeprom.ops if op[1] < 0x800]
        assert touched, hex(entry)
        for op in touched:
            assert op[1] % 64 + op[2] <= 22, (hex(entry), op[:3])
        for s in SLOTS:
            assert rig.eeprom.data[s + 22:s + 64] == sentinel[s + 22:s + 64], hex(entry)
        runs += 1
    return {'eeprom_call_sites': len(sites), 'i2c_driver_call_sites': sorted(map(hex, drivers)), 'pattern_paths_run': runs}


SLOT_SENTINEL = L.SLOT_ADDRESS


# ---------------------------------------------------------------- start-up

def random_eeprom(rng):
    data = bytearray(rng.randbytes(0x8000))
    truth = []
    for s in SLOTS:
        kind = rng.choice(('valid', 'valid', 'valid', 'tag', 'long', 'check', 'blank', 'zero', 'random'))
        lengths = [rng.choice((0, 0, rng.randint(1, 16))) for _ in range(8)]
        rec = bytearray(record(lengths))
        if kind == 'tag': rec[0] ^= 0x01; rec[9] = ~sum(rec[:9]) & 0xFF
        elif kind == 'long': rec[1 + rng.randrange(8)] = rng.randint(17, 255); rec[9] = ~sum(rec[:9]) & 0xFF
        elif kind == 'check': rec[9] ^= 1 << rng.randrange(8)
        elif kind == 'blank': rec = bytearray(b'\xff' * 10)
        elif kind == 'zero': rec = bytearray(10)
        elif kind == 'random': rec = bytearray(rng.randbytes(10))
        data[s + L.RECORD:s + L.RECORD + 10] = rec
        truth.append(lengths_of(rec) or [0] * 8)
    return data, truth


def check_boot(image, rng):
    cases = 0
    for case in range(200):
        data, truth = random_eeprom(rng)
        rig = Rig(image, extra=new_ranges(), eeprom=EEPROM(data))
        slot_address = rng.choice((0, rng.randrange(32) * 64, 0xFFFF, 0x800, 0x41))
        rig.poke(L.SLOT_ADDRESS, slot_address, 2)
        regs = {f'r{i}': 0xB0000000 + i for i in range(4, 12)}
        assert rig.run(L.ADDRESS['BOOT'], **regs) == STOP
        assert [rig.vm.regs[i] for i in range(4, 12)] == list(regs.values())
        assert rig.stubbed == [L.LAST_INIT], 'the replaced start-up call runs first'
        assert rig.eeprom.ops == [('read', s + L.RECORD, 10) for s in SLOTS], 'one read per slot, nothing written'
        assert rig.st(L.LOADED) == 1 and all(rig.cache(s) == truth[s] for s in range(32))
        valid = slot_address % 64 == 0 and slot_address < 0x800
        assert rig.lens() == (truth[slot_address // 64] if valid else [0] * 8), (case, hex(slot_address))
        cases += 1
    return cases


# ---------------------------------------------------------------- pattern loads

def check_loads(midi, image, rng):
    cases = loads = 0
    for case in range(300):
        data, truth = random_eeprom(rng)
        for s in SLOTS:                                      # some patterns need the tidy-up's own save
            if rng.random() < 0.2: data[s + 1] = rng.randint(4, 255); data[s + 2] = rng.choice((0, 17, 200))
        state = dict(mode=rng.choice((0, 1, 2, 2, 3)), pattern=rng.randrange(16), group=rng.randrange(2),
                     loaded=rng.choice((0, 0x40 * rng.randrange(32), 0xFFFF)), song=rng.randrange(256),
                     songstep=rng.randrange(0xFD), busy=rng.choice((0, 1)), ready=rng.random() < 0.8)
        results = []
        for img, new in ((midi, False), (image, True)):
            rig = Rig(img, [LOAD_PATTERN], extra=new_ranges() if new else (), eeprom=EEPROM(data))
            rig.poke(0x20000260, state['mode'], 1); rig.poke(0x200009C0, state['pattern'])
            rig.poke(0x200009CC, state['group'], 1); rig.poke(L.SLOT_ADDRESS, state['loaded'], 2)
            rig.poke(0x20000238, state['busy']); rig.poke(0x2000029C, state['songstep'], 1)
            for i in range(0xFD): rig.poke(0x20000AB4 + i, (state['song'] + 7 * i) % 32, 1)
            for i in range(8): rig.poke(LEN_AT + i, 0x11 + i, 1)
            if new and state['ready']:
                rig.set_st(L.LOADED, 1)
                for s in range(32):
                    for i in range(8): rig.set_st(L.CACHE + 8 * s + i, truth[s][i])
            assert rig.run(LOAD_PATTERN, {LOAD_TAIL}) == LOAD_TAIL
            results.append((rig, bytes(rig.ram.data)))
        (a, ra), (b, rb) = results
        assert a.eeprom.ops == b.eeprom.ops and a.eeprom.data == b.eeprom.data, case
        lens = set(range(LEN_AT - 0x20000000, LEN_AT - 0x20000000 + 8))
        diff = {i for i in range(16384) if ra[i] != rb[i]}
        assert diff <= lens | C.STACK_BYTES | STATE, sorted(hex(0x20000000 + i) for i in diff - lens - C.STACK_BYTES - STATE)
        reloaded = any(op[0] == 'read' and op[2] == 22 for op in b.eeprom.ops)
        slot = b.peek(L.SLOT_ADDRESS, 2)
        if reloaded and state['ready'] and slot % 64 == 0 and slot < 0x800:
            assert b.lens() == truth[slot // 64], case
            loads += 1
        else:
            assert b.lens() == [0x11 + i for i in range(8)], case
        cases += 1
    return cases, loads


# ---------------------------------------------------------------- buttons

PANEL_MACHINE = C.panel_machine


def panel_rig(image, new):
    m = PANEL_MACHINE(image, True)
    if new:
        for name in L.ORDER:
            a, b = code_of(name, L)
            m.vm.program.add('LEN ' + name, a, image[a - BASE:b - BASE])
    return m


class Panel(C.Panel):
    def __init__(self, image):
        self.m = panel_rig(image, True)
        self.m.poke(V.PATTERN + 2, 16, 1)
        self.tick = 1000


def check_panel(midi, image, rng):
    # Every v1.3 gesture, unchanged (check_scatter_v1_3 builds its machine through panel_machine).
    original = C.panel_machine
    C.panel_machine = lambda img, v13: panel_rig(img, img is image)
    try: C.check_panel_gestures(image)
    finally: C.panel_machine = original
    # Setting a length stores it for the playing pattern's slot and marks the slot.
    F, TAP, step = V.KEY_FUNCTION, V.KEY_TAP, lambda k: V.KEY_STEP1 + k - 1
    cases = 0
    for slot_address, ready in ((0x40 * 9, 1), (0, 1), (0x7C0, 1), (0x40 * 9, 0), (0xFFFF, 1), (0x45, 1)):
        p = Panel(image)
        p.m.poke(L.SLOT_ADDRESS, slot_address, 2); p.m.set_st(L.LOADED, ready)
        p.click(F, gap=4000); p.click(F, gap=300)
        assert p.st(V.MUTEMODE) == 1
        valid = ready and slot_address % 64 == 0 and slot_address < 0x800
        slot = slot_address // 64
        for voice, length in ((3, 5), (8, 16), (1, 1)):
            p.press(step(voice)); p.run(advance=V.WINDOW); p.press(step(length)); p.release(step(length)); p.release(step(voice))
            assert p.st(V.LEN + voice) == length
            assert p.st(L.CACHE + 8 * slot + voice - 1) == (length if valid else 0) if slot < 32 else True
        assert p.st(L.DIRTY, 4) == ((1 << slot) if valid else 0)
        p.m.set_st(L.DIRTY, 0, 4); p.m.set_st(L.FAILS, 2)
        p.press(step(3)); p.press(TAP); p.release(TAP); p.release(step(3))
        assert p.st(V.LEN + 3) == 0
        if valid:
            assert p.st(L.CACHE + 8 * slot + 2) == 0 and p.st(L.DIRTY, 4) == 1 << slot and p.st(L.FAILS) == 0
        cases += 1
    # 3,000 random panel ticks: the same as the MIDI build, apart from the new state.
    a, b = panel_rig(midi, False), panel_rig(image, True)
    states = (0, 1, 3, 4, 7)
    for _ in range(3000):
        keys = {i: rng.choice(states) if rng.random() < 0.3 else 0 for i in range(21)}
        mode, playing, busy = rng.choice((2, 2, 2, 3, 1, 0)), rng.choice((1, 1, 0)), rng.choice((0, 0, 1))
        seed = rng.getrandbits(32)
        results = []
        for m in (a, b):
            m.ram.data[:] = bytes(16384)
            r = random.Random(seed)
            m.set_st(V.MUTEMODE, r.choice((0, 1))); m.set_st(V.HELD, r.choice((0, 0, 3, 7)))
            m.set_st(V.HELD_T, r.getrandbits(8), 4); m.set_st(V.TICK, 5000, 4)
            m.poke(L.SLOT_ADDRESS, r.randrange(32) * 64, 2); m.set_st(L.LOADED, 1)
            exit_pc = C.panel(m, keys, mode, playing, busy)
            results.append((exit_pc, bytes(m.ram.data)))
        (e1, r1), (e2, r2) = results
        assert e1 == e2
        diff = {i for i in range(16384) if r1[i] != r2[i]}
        assert diff <= STATE | C.STACK_BYTES, sorted(hex(0x20000000 + i) for i in diff - STATE - C.STACK_BYTES)
        cases += 1
    return cases


# ---------------------------------------------------------------- saving

def saver(image, new, data):
    rig = Rig(image, [SAVER], extra=new_ranges() if new else (), eeprom=EEPROM(data))
    return rig


def stock_save_state(rig, r):
    """Random stock save state: a dirty playing pattern and song, and the save request."""
    rig.poke(SAVE_REQUEST, r.choice((0, 1, 1)))
    rig.poke(0x2000028C, r.choice((0, 1))); rig.poke(0x20000290, r.choice((0, 1)))
    rig.poke(0x200009C0, r.randrange(16)); rig.poke(0x20000224, r.randrange(2), 1)
    rig.poke(0x20000278, r.randrange(8), 1)
    for i in range(22): rig.poke(PLAYING_PATTERN + i, r.getrandbits(8), 1)
    for i in range(0xFD): rig.poke(0x20000AB4 + i, r.getrandbits(8), 1)


def check_saves(midi, image, rng):
    cases = written = 0
    # Nothing marked: exactly the MIDI build's stock saves.
    for case in range(150):
        data = bytearray(rng.randbytes(0x8000)); seed = rng.getrandbits(32)
        rigs = []
        for img, new in ((midi, False), (image, True)):
            rig = saver(img, new, data)
            stock_save_state(rig, random.Random(seed))
            if new: rig.set_st(L.LOADED, rng.choice((0, 1)))
            assert rig.run(SAVER, {SAVER_TAIL}) in (STOP, SAVER_TAIL)
            rigs.append(rig)
        a, b = rigs
        assert a.eeprom.ops == b.eeprom.ops and a.eeprom.data == b.eeprom.data, case
        cases += 1
    # Marked slots: one record per save, lowest slot first, after the pattern, read back.
    for case in range(100):
        data = bytearray(rng.randbytes(0x8000)); before = bytes(data)
        rig = saver(image, True, data)
        r = random.Random(rng.getrandbits(32))
        stock_save_state(rig, r); rig.poke(0x2000028C, 0); rig.poke(0x20000290, 0)
        rig.set_st(L.LOADED, 1)
        marked = sorted(rng.sample(range(32), rng.randint(1, 4)))
        cache = {s: [rng.choice((0, rng.randint(1, 16))) for _ in range(8)] for s in range(32)}
        for s in range(32):
            for i in range(8): rig.set_st(L.CACHE + 8 * s + i, cache[s][i])
        rig.set_st(L.DIRTY, sum(1 << s for s in marked), 4)
        for n, s in enumerate(marked):
            rig.eeprom.ops.clear(); rig.poke(SAVE_REQUEST, 1)
            rig.run(SAVER, {SAVER_TAIL})
            ours = [op for op in rig.eeprom.ops if op[1] < 0x800]
            assert ours == [('write', s * 64 + L.RECORD, 10, record(cache[s])), ('read', s * 64 + L.RECORD, 10)], (case, ours)
            assert rig.st(L.DIRTY, 4) == sum(1 << t for t in marked[n + 1:]) and rig.st(L.FAILS) == 0
            written += 1
        rig.eeprom.ops.clear(); rig.poke(SAVE_REQUEST, 1); rig.run(SAVER, {SAVER_TAIL})
        assert not [op for op in rig.eeprom.ops if op[1] < 0x800], 'nothing left to save'
        rig.eeprom.ops.clear(); rig.poke(SAVE_REQUEST, 0); rig.set_st(L.DIRTY, 1, 4); rig.run(SAVER, {SAVER_TAIL})
        assert rig.eeprom.ops == [] and rig.st(L.DIRTY, 4) == 1, 'no save request, no save'
        changed = {i for i in range(0x8000) if rig.eeprom.data[i] != before[i]}
        assert changed <= {s * 64 + L.RECORD + i for s in marked for i in range(10)} | set(range(0x1000, 0x1800)), sorted(map(hex, changed))[:5]
        cases += 1
    # A write that doesn't stick: retried at the next 3 saves, then dropped.
    for drops in (1, 2, 3, 4, 9):
        data = bytearray(rng.randbytes(0x8000))
        rig = saver(image, True, data)
        rig.set_st(L.LOADED, 1); rig.set_st(L.DIRTY, 1 << 5, 4)
        for i in range(8): rig.set_st(L.CACHE + 40 + i, i + 1)
        left = [drops]
        def drop(address, n):
            if address == 5 * 64 + L.RECORD and left[0]: left[0] -= 1; return True
            return False
        rig.eeprom.drop = drop
        attempts = 0
        for _ in range(8):
            rig.poke(SAVE_REQUEST, 1); rig.run(SAVER, {SAVER_TAIL})
            attempts = sum(1 for op in rig.eeprom.ops if op[0] == 'write' and op[1] == 5 * 64 + L.RECORD)
            if not rig.st(L.DIRTY, 4): break
        saved = rig.eeprom.data[5 * 64 + L.RECORD:5 * 64 + L.RECORD + 10] == record(range(1, 9))
        assert attempts == min(drops + 1, 4) and saved == (drops <= 3) and rig.st(L.FAILS) == 0, (drops, attempts, saved)
        cases += 1
    return cases, written


# ---------------------------------------------------------------- round trips

def check_round_trips(image, rng):
    """Sessions of setting lengths, changing patterns and saving, then a power cycle."""
    cases = 0
    for session in range(40):
        data = bytearray(rng.randbytes(0x8000))
        for s in SLOTS:
            data[s + 1] %= 4; data[s + 2] = data[s + 2] % 16 + 1
            if rng.random() < 0.3: data[s + L.RECORD:s + L.RECORD + 10] = record([rng.randint(0, 16) for _ in range(8)])
        eeprom = EEPROM(data)
        pattern_bytes = {s: bytes(data[s:s + 22]) for s in SLOTS}
        expected = {s // 64: lengths_of(data[s + L.RECORD:s + L.RECORD + 10]) or [0] * 8 for s in SLOTS}
        boot = Rig(image, extra=new_ranges(), eeprom=eeprom)
        boot.run(L.ADDRESS['BOOT'])
        ram = bytes(boot.ram.data)
        load = Rig(image, [LOAD_PATTERN], extra=new_ranges(), eeprom=eeprom)
        panel = panel_rig(image, True)
        save = saver(image, True, eeprom.data); save.eeprom = eeprom
        for event in range(30):
            for r in (load, save): r.ram.data[:] = ram
            panel.ram.data[:] = ram
            kind = rng.choice(('load', 'set', 'set', 'save'))
            if kind == 'load':
                load.poke(0x20000260, 2, 1); load.poke(0x200009C0, rng.randrange(16)); load.poke(0x200009CC, rng.randrange(2), 1)
                load.run(LOAD_PATTERN, {LOAD_TAIL}); ram = bytes(load.ram.data)
            elif kind == 'set':
                slot = load.peek(L.SLOT_ADDRESS, 2) // 64 if load.peek(L.SLOT_ADDRESS, 2) < 0x800 else None
                voice, length = rng.randint(1, 8), rng.choice((0, rng.randint(1, 16)))
                # set_length as PANEL calls it: r0 = ST + row, r1 = length, r7 = ST
                assert panel.run(L.ADDRESS['SET'], set(), r0=V.ST + voice, r1=length, r7=V.ST) == STOP
                ram = bytes(panel.ram.data)
                if slot is not None and panel.peek(L.SLOT_ADDRESS, 2) % 64 == 0: expected[slot][voice - 1] = length
            else:
                save.poke(SAVE_REQUEST, 1); save.run(SAVER, {SAVER_TAIL}); ram = bytes(save.ram.data)
        for _ in range(33):                                  # the remaining saves
            save.ram.data[:] = ram; save.poke(SAVE_REQUEST, 1); save.run(SAVER, {SAVER_TAIL}); ram = bytes(save.ram.data)
        assert save.st(L.DIRTY, 4) == 0
        # Power cycle: fresh RAM, start-up, then every pattern in turn.
        boot = Rig(image, extra=new_ranges(), eeprom=eeprom)
        boot.run(L.ADDRESS['BOOT']); ram = bytes(boot.ram.data)
        for s in range(32):
            load.ram.data[:] = ram
            load.poke(0x20000260, 2, 1); load.poke(0x200009C0, s % 16); load.poke(0x200009CC, s // 16, 1)
            load.poke(L.SLOT_ADDRESS, 0xFFFF, 2)
            load.run(LOAD_PATTERN, {LOAD_TAIL})
            assert load.lens() == expected[s], (session, s, load.lens(), expected[s])
        assert all(bytes(eeprom.data[s:s + 22]) == pattern_bytes[s] for s in SLOTS), 'no pattern byte changed'
        cases += 1
    return cases


# ---------------------------------------------------------------- Pattern Write's lights

LIGHTS, LIGHT_LOOP, LED_WORD, LED_TABLE = 0x0800641C, 0x08006502, 0x20000A38, 0x0800AE9C


def check_lights(midi, image, rng):
    """The light builder (main loop) beside the MIDI build, in every mode, playing or not: the
    same lights, except in Pattern Write while playing with a voice of its own length selected.
    Then the running light is on the step that voice last played and its steps past its
    length are dark."""
    table = [int.from_bytes(image[LED_TABLE - BASE + 4 * i:LED_TABLE - BASE + 4 * i + 4], 'little') for i in range(16)]
    rigs = {new: Rig(img, [LIGHTS], extra=new_ranges() if new else ()) for img, new in ((midi, False), (image, True))}
    cases = shown = 0
    for case in range(2000):
        r = random.Random(rng.getrandbits(32))
        mode = r.choice((3, 3, 3, 3, 2, 2, 1, 0))
        playing, scale = r.random() < 0.85, r.random() < 0.1
        k = r.randrange(9)
        row_pointer = r.choice([L.ROW0 + 2 * k] * 8 + [L.ROW0 - 2, L.ROW0 + 18])   # the stock code sets even row addresses
        length = r.randint(1, 16); clock = r.randrange(length)
        rows = [r.getrandbits(16) for _ in range(9)]
        lens = [0] + [r.choice((0, r.randint(1, 16))) for _ in range(8)]
        steps = r.choice((0, r.randrange(1, 3000)))
        snapshot = r.choice((0, 0xD1000000 | (r.randrange(length) << 10) | (length << 5) | clock))
        runs = {}
        for new, rig in rigs.items():
            rig.ram.data[:] = bytes(16384)
            rig.poke(V.MODE_BYTE, mode, 1); rig.poke(V.TRANSPORT, int(playing)); rig.poke(0x20000BBC, clock, 1)
            rig.poke(L.SCALE_SHOWN, int(scale)); rig.poke(L.SELECTED_ROW, row_pointer)
            rig.poke(V.PATTERN + 2, length, 1)
            for i, row in enumerate(rows): rig.poke(V.PATTERN + 4 + 2 * i, row, 2)
            rig.poke(0x20002070, snapshot)
            rig.poke(0x200009C8, length - 1); rig.poke(LED_WORD, 0x5A5A0000)
            for i, value in enumerate(lens): rig.set_st(V.LEN + i, value)
            rig.set_st(V.N, steps, 4)
            seen = []
            rig.vm.observers[LIGHT_LOOP] = [lambda vm, rig=rig, seen=seen: seen.append((vm.regs[0], rig.peek(LED_WORD)))]
            rig.run(LIGHTS)
            runs[new] = (seen, bytes(rig.ram.data))
        (seen_a, ram_a), (seen_b, ram_b) = runs[False], runs[True]
        valid_row = row_pointer in [L.ROW0 + 2 * i for i in range(9)]
        own = lens[(row_pointer - L.ROW0) // 2] if valid_row else 0
        if mode == 3 and playing and not scale and own:
            (bits_a, before_a), (bits_b, before_b) = seen_a[0], seen_b[0]   # the loop's first pass
            row = rows[(row_pointer - L.ROW0) // 2]
            v12_step = (bits_a ^ row).bit_length() - 1            # the MIDI build's running light
            assert bits_a ^ row == 1 << v12_step
            at = (steps - 1) % own if steps else v12_step
            want = (row & ((1 << own) - 1)) ^ (1 << at)
            assert bits_b == want and before_b == before_a, (case, hex(bits_b), hex(want))
            led = before_b
            for i in range(16):
                if want >> i & 1: led |= table[i]
            assert int.from_bytes(ram_b[LED_WORD - 0x20000000:LED_WORD - 0x20000000 + 4], 'little') == led
            word = set(range(LED_WORD - 0x20000000, LED_WORD - 0x20000000 + 4))
            diff = {i for i in range(16384) if ram_a[i] != ram_b[i]}
            assert diff <= word | C.STACK_BYTES, sorted(hex(0x20000000 + i) for i in diff - word - C.STACK_BYTES)
            shown += 1
        else:
            assert seen_a == seen_b, case
            diff = {i for i in range(16384) if ram_a[i] != ram_b[i]}
            assert diff <= C.STACK_BYTES, (case, sorted(hex(0x20000000 + i) for i in diff - C.STACK_BYTES))
        cases += 1
    return cases, shown


# ---------------------------------------------------------------- bounds

def check_bounds(image):
    """LOAD runs in the timers: count what it adds to a pattern load. SET masks interrupts:
    count its longest masked run."""
    rig = Rig(image, extra=new_ranges())
    rig.set_st(L.LOADED, 1); rig.poke(L.SLOT_ADDRESS, 0x7C0, 2)
    rig.vm.reset_statistics()
    rig.run(L.ADDRESS['APPLY'], r0=0x7C0, r4=V.ST)
    apply_steps = rig.vm.stats['instructions']
    longest = 0
    for slot_address, ready in ((0x7C0, 1), (0, 1), (0xFFFF, 1), (0x40, 0)):
        rig.poke(L.SLOT_ADDRESS, slot_address, 2); rig.set_st(L.LOADED, ready)
        vm = rig.vm
        vm.regs[0], vm.regs[1], vm.regs[7] = V.ST + 4, 9, V.ST
        vm.regs[13], vm.regs[14], vm.regs[15] = SP, STOP | 1, L.ADDRESS['SET']
        run = 0
        while vm.regs[15] != STOP:
            masked = vm.primask
            vm.step()
            run = run + 1 if masked else 0
            longest = max(longest, run)
        assert not vm.primask
    return {'apply_instructions': apply_steps, 'set_max_masked_instructions': longest}


def main():
    rng = random.Random(1414)
    stock_syx = (HERE / 'firmware/RD-6_V1.0.5.syx').read_bytes()
    stock = bytes(decode(stock_syx, 100)[3])
    midi = bytes(decode(apply(stock_syx, json.loads(MIDI.read_text())))[3])
    syx, image = build(stock_syx)
    assert apply(stock_syx, json.loads(OUT.read_text())) == syx, 'the published patch is the build'
    changed, run = check_bytes(midi, image)
    report = {
        'build': 'SCATTER_V1_4',
        'syx_sha256': hashlib.sha256(syx).hexdigest(),
        'image_sha256': hashlib.sha256(image).hexdigest(),
        'bytes_changed_from_midi_test': changed,
        'mask_run_blocks': run,
        'stock_eeprom_audit': audit(stock),
        'start_up_cases': check_boot(image, rng),
        'pattern_load_cases_and_reloads': check_loads(midi, image, rng),
        'panel_cases': check_panel(midi, image, rng),
        'save_cases_and_records_written': check_saves(midi, image, rng),
        'round_trip_sessions': check_round_trips(image, rng),
        'light_cases_and_own_length_displays': check_lights(midi, image, rng),
        'bounds': check_bounds(image),
        'status': 'passed_scatter_v1_4',
    }
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
