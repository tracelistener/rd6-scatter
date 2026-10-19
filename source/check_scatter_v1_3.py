"""Offline checks for Scatter v1.3 (source/mute_roll.py).

1. Bytes: it differs from Scatter v1.2 only at the six listed sites and in the five
   new routines, every branch matches the listing, the header checksum is right, and
   the updater can still recover the mask (at least 64 identical blocks).
2. Unchanged with the new state at zero (as at power-on): the step dispatcher, run
   from its entry through Scatter's step hook, makes exactly the same GPIO writes,
   MIDI notes and RAM changes as v1.2 for random patterns, steps and Scatter step
   masks (including silenced steps); so do the trigger countdown, the light builder,
   the extra-hit filter and the Pattern Play buttons.
3. Mutes, accent mute, rolls at every rate, own lengths over 96 steps, silenced
   steps and restarts follow a Python model of the rules in source/mute_roll.py,
   checked on the actual trigger pins and MIDI notes. The 1/32 roll's second hit
   fires half a step later on the right pins and gets a regular 16-tick trigger.
4. Buttons: the double-click (clean presses only, within the window, on release),
   every gesture in the mode, which keys are marked handled, the step lights, and
   the mode ending when playback stops or leaves Pattern Play.
Decoding stays in memory; no decrypted file is written.
"""
from pathlib import Path
import hashlib, json, random, sys
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'source')); sys.path.insert(0, str(HERE / 'scripts'))
from apply_patch import apply
from build_scatter_v1_2 import longest_run
from build_scatter_v1_3 import decode, MIN_RUN
from rd6_thumb_machine import Program, Memory, Thumb, MachineFault
import mode_keep as MK
import mute_roll as M

BASE = 0x08002800
STOP_LR = 0x08001000
SP_TOP = 0x20003F00
KEYS, STATE, AUX, COMMAND = 0x20000914, 0x2000202C, 0x20000230, 0x20002000
DISPATCHER = (0x08006AE0, 0x08006C44)
STEP_HOOK = (0x0800BB90, 0x0800BBDE)
COUNTDOWN = (0x08006DBC, 0x08006E3A)
RELEASE = (0x08002E48, 0x08002E6A)
LIGHT_LOOP = (0x080064FE, 0x0800651C)
LIGHT_POP = (0x0800649A, 0x0800649E)
CONSUME = (0x0800BE00, 0x0800BE7A)          # rd6_panel_release_stock_step and rd6_panel_consume
LIGHT_WORD, LED_TABLE = 0x20000A34, 0x0800AE9C
SCATTER_CONFIG, SOURCE_MASK, SNAPSHOT = 0x0800B4C8, 0x0800B47C, 0x0800B87C
MIDI_QUEUE, CALIBRATED_DELAY, CLAP_PRE = 0x08002DD4, 0x08003196, 0x08002EE4
CONTINUE, CANCEL, KEEP = M.PANEL_CONTINUE, 0x0800BF32, M.PANEL_KEEP
SHORT_COUNTER, CLAP_COUNTER = 0x20001198, 0x2000119C
# row -> (port, pin) and MIDI note; the dispatcher fires BD SD LT HT CY OH CH CP in that order
PINS = {1: ('C', 0x2000), 2: ('C', 0x4000), 3: ('C', 0x8000), 4: ('C', 0x0001), 5: ('B', 0x8000),
        6: ('C', 0x0200), 7: ('C', 0x0002), 8: ('C', 0x0004)}
NOTES = {1: 0x24, 2: 0x28, 3: 0x2D, 4: 0x32, 5: 0x33, 7: 0x2E, 8: 0x2A, 6: 0x27}
MIDI_ORDER = (1, 2, 3, 4, 5, 7, 8, 6)
ST_BYTES = set(range(M.ST - 0x20000000, M.ST - 0x20000000 + M.SIZE + 2))
STACK_BYTES = set(range(SP_TOP - 0x200 - 0x20000000, SP_TOP + 0x40 - 0x20000000))


class Port:
    """GPIO port: OCTL (+0x14) read, BOP (+0x18) and BC (+0x28) writes, logged."""
    def __init__(self, name, base):
        self.name, self.base, self.octl, self.writes = name, base, 0, []
    def read(self, address, size):
        if address - self.base != 0x14 or size != 4: raise MachineFault(f'{self.name}: unexpected read {address:#x}')
        return self.octl
    def write(self, address, size, value):
        offset = address - self.base
        if offset == 0x18 and size == 4: self.octl = (self.octl | (value & 0xFFFF)) & ~(value >> 16) & 0xFFFF
        elif offset == 0x28 and size == 4: self.octl &= ~value & 0xFFFF
        else: raise MachineFault(f'{self.name}: unexpected write {address:#x}')
        self.writes.append((offset, value))


def code_end(name):
    """End of a routine's instructions (its data tables follow)."""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    instrs, _ = M.parse(M.SOURCE[name])
    last = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(M.BODY[name], M.ADDRESS[name], len(instrs)))[-1]
    return last.address + last.size


class Machine:
    def __init__(self, image, ranges, v13):
        program = Program()
        for name, (start, end) in ranges.items(): program.add(name, start, image[start - BASE:end - BASE])
        if v13:
            for name in M.ORDER: program.add(name, M.ADDRESS[name], image[M.ADDRESS[name] - BASE:code_end(name) - BASE])
        self.memory = Memory()
        self.memory.add('flash', BASE, image)
        self.ram = self.memory.add('ram', 0x20000000, 16384, writable=True)
        self.c, self.b = Port('GPIOC', 0x48000800), Port('GPIOB', 0x48000400)
        for port in (self.b, self.c):
            self.memory.add(port.name, port.base, 0x30, writable=True, read_hook=port.read, write_hook=port.write)
        self.vm = Thumb(self.memory, program)
        self.calls, self.mask = [], 0
        def log(name, argument=True): return lambda vm: self.calls.append((name, vm.regs[0] if argument else None))
        for address, name in ((MIDI_QUEUE, 'midi'), (CALIBRATED_DELAY, 'delay'), (SNAPSHOT, 'snapshot')):
            self.vm.intercepts[address] = log(name)
        self.vm.intercepts[CLAP_PRE] = log('clap_pre', False)   # 0x08002EE4 takes no argument: it loads r0 first
        self.vm.intercepts[SCATTER_CONFIG] = lambda vm: vm.regs.__setitem__(0, 0)
        self.vm.intercepts[SOURCE_MASK] = lambda vm: vm.regs.__setitem__(0, self.mask)

    def clear_logs(self):
        self.c.writes.clear(); self.b.writes.clear(); self.calls.clear()

    def poke(self, address, value, size=4): self.memory.poke(address, value, size)
    def peek(self, address, size=4): return self.memory.peek(address, size)
    def st(self, offset, size=1): return self.peek(M.ST + offset, size)
    def set_st(self, offset, value, size=1): self.poke(M.ST + offset, value, size)

    def run(self, entry, stops, frame=(), max_steps=20000, **regs):
        vm = self.vm
        sp = SP_TOP - 4 * len(frame)
        for i, word in enumerate(frame): self.poke(sp + 4 * i, word)
        for name, value in regs.items(): vm.regs[int(name[1:])] = value
        vm.regs[13], vm.regs[14] = sp, STOP_LR | 1
        status, _ = vm.run(entry, stops | {STOP_LR}, max_steps)
        assert status == 'stop', status
        return vm.regs[15]


# ---------------------------------------------------------------- dispatcher

def dispatcher(image, v13):
    return Machine(image, {'dispatcher': DISPATCHER, 'step hook': STEP_HOOK}, v13)


def setup_step(m, rows, length, step, mask, playing=1, mode=2):
    m.poke(0x20000BB4, playing); m.poke(0x20000BBC, step, 1); m.poke(M.MODE_BYTE, mode, 1)
    m.poke(0x2000022C, 0)
    m.poke(M.PATTERN + 2, length, 1)
    for lane, row in enumerate(rows): m.poke(M.PATTERN + 4 + 2 * lane, row, 2)
    m.mask = mask
    m.clear_logs()


def step(m):
    exit_pc = m.run(DISPATCHER[0], set())
    assert exit_pc == STOP_LR
    fired, accent = 0, None
    for port, writes in (('C', m.c.writes), ('B', m.b.writes)):
        for offset, value in writes:
            if port == 'C' and value == 0x40: accent = offset == 0x18
            if offset != 0x18: continue
            for lane, (p, pin) in PINS.items():
                if p == port and value == pin: fired |= 1 << lane
    notes = [value for name, value in m.calls if name == 'midi']
    return fired | (1 if accent else 0), notes, list(m.c.writes), list(m.b.writes), list(m.calls)


def model(rows, mask, n, lens, rate, rolls, mutes):
    """The step's hits before and after mutes, per source/mute_roll.py."""
    hits = 0
    for lane in range(9):
        if lens[lane]:
            if mask and rows[lane] >> (n % lens[lane]) & 1: hits |= 1 << lane
        elif rows[lane] & mask: hits |= 1 << lane
    if rate and n % M.ROLL_STEPS[rate] == 0: hits |= rolls
    return hits & ~mutes, hits


def expected_notes(hits):
    accent = 0x80 if hits & 1 else 0
    return [NOTES[lane] | accent for lane in MIDI_ORDER if hits >> lane & 1]


def check_dispatcher_unchanged(v12, v13, rng):
    a, b = dispatcher(v12, False), dispatcher(v13, True)
    cases = 0
    for case in range(600):
        rows = [rng.getrandbits(16) for _ in range(9)]
        length = rng.randint(1, 16)
        clock = rng.randrange(length)
        mask = rng.choice([1 << clock, 1 << rng.randrange(16), 0])
        results = []
        for m in (a, b):
            m.ram.data[:] = bytes(16384)
            setup_step(m, rows, length, clock, mask)
            fired, notes, cw, bw, calls = step(m)
            ram = bytes(m.ram.data)
            results.append((fired, notes, cw, bw, calls, ram))
        (f1, n1, c1, b1, k1, r1), (f2, n2, c2, b2, k2, r2) = results
        assert (f1, n1, c1, b1, k1) == (f2, n2, c2, b2, k2), (case, hex(mask), f1, f2)
        diff = {i for i in range(16384) if r1[i] != r2[i]}
        assert diff <= ST_BYTES | STACK_BYTES, sorted(hex(0x20000000 + i) for i in diff - ST_BYTES - STACK_BYTES)
        expected_hits, _ = model(rows, mask, 0, [0] * 9, 0, 0, 0)
        assert f2 == expected_hits and n2 == expected_notes(expected_hits), (case, f2, expected_hits)
        cases += 1
    return cases


def check_features(v13, rng):
    m = dispatcher(v13, True)
    counted = 0
    for trial in range(60):
        m.ram.data[:] = bytes(16384)
        lens = [0] + [rng.choice([0, 0, rng.randint(1, 16)]) for _ in range(8)]
        rate = rng.randrange(6)
        rolls = rng.getrandbits(8) << 1 if rng.random() < 0.7 else 0
        mutes = rng.getrandbits(9) if rng.random() < 0.7 else 0
        m.set_st(M.RESTART, 1)                      # as after a stop: no previous step to measure
        for lane, value in enumerate(lens): m.set_st(M.LEN + lane, value)
        m.set_st(M.RATE, rate); m.set_st(M.ROLLS, rolls, 2); m.set_st(M.MUTES, mutes, 2)
        rows = [rng.getrandbits(16) for _ in range(9)]
        length = rng.randint(1, 16)
        tick = 5000
        for n in range(96):
            clock = n % length
            mask = 0 if rng.random() < 0.1 else (1 << clock if rng.random() < 0.8 else 1 << rng.randrange(16))
            tick += 77
            m.set_st(M.TICK, tick, 4)
            setup_step(m, rows, length, clock, mask)
            fired, notes, *_ = step(m)
            hits, before = model(rows, mask, n, lens, rate, rolls, mutes)
            assert fired == hits and notes == expected_notes(hits), (trial, n, bin(fired), bin(hits))
            assert m.st(M.HPRE, 2) == before and m.st(M.N, 4) == n + 1
            assert m.st(M.LENMASK, 2) == sum(1 << lane for lane in range(9) if lens[lane])
            mid_pins = rolls & ~mutes & M.NO_CLAP if rate == 1 else 0
            want_mid = 77 // 2 if mid_pins and n > 0 else 0
            assert m.st(M.MID, 2) == want_mid, (n, m.st(M.MID, 2), want_mid)
            counted += 1
        # a stop restarts the count: the next step is step 0 again
        m.set_st(M.RESTART, 1)
        tick += 77; m.set_st(M.TICK, tick, 4)
        setup_step(m, rows, length, 0, 1)
        fired, _, *_ = step(m)
        assert fired == model(rows, 1, 0, lens, rate, rolls, mutes)[0] and m.st(M.N, 4) == 1 and m.st(M.MID, 2) == 0
    return counted


# ---------------------------------------------------------------- countdown and 1/32 hits

def countdown(image, v13):
    return Machine(image, {'countdown': COUNTDOWN, 'release': RELEASE}, v13)


def check_countdown_unchanged(v12, v13):
    a, b = countdown(v12, False), countdown(v13, True)
    cases = 0
    for short in (0, 1, 2, 3, 4, 5, 6, 7, 16, 17, 18, 19, 20, 21):
        for clap in (0, 1, 10, 11, 109, 110, 111, 120, 121, 220, 221, 230, 231, 330, 331, 339, 340):
            for flag in (0, 1):
                for playing, mode in ((1, 2), (0, 2), (1, 3)):
                    results = []
                    for m in (a, b):
                        m.ram.data[:] = bytes(16384); m.clear_logs()
                        m.poke(SHORT_COUNTER, short); m.poke(CLAP_COUNTER, clap); m.poke(0x200011A4, 1)
                        m.poke(M.SHORT_FLAG, flag); m.poke(M.TRANSPORT, playing); m.poke(M.MODE_BYTE, mode, 1)
                        m.c.octl, m.b.octl = 0xE387, 0x8000
                        assert m.run(COUNTDOWN[0], set()) == STOP_LR
                        results.append((bytes(m.ram.data), list(m.c.writes), list(m.b.writes)))
                    (r1, c1, b1), (r2, c2, b2) = results
                    assert (c1, b1) == (c2, b2), (short, clap, flag, playing)
                    diff = {i for i in range(16384) if r1[i] != r2[i]}
                    assert diff <= ST_BYTES | STACK_BYTES, sorted(hex(0x20000000 + i) for i in diff)
                    cases += 1
    return cases


def check_mid_hit(v13):
    """1/32: the second hit fires half a step later on the rolled pins, with a regular trigger."""
    d = dispatcher(v13, True)
    rows = [0] * 9
    d.set_st(M.RATE, 1); d.set_st(M.ROLLS, (1 << 1) | (1 << 5) | (1 << 6) | (1 << 7), 2); d.set_st(M.MUTES, 1 << 7, 2)
    for n, tick in enumerate((1000, 1100)):
        d.set_st(M.TICK, tick, 4)
        setup_step(d, rows, 16, n, 1 << n)
        fired, *_ = step(d)
        assert fired == (1 << 1) | (1 << 5) | (1 << 6)            # BD, CY, CP rolled; OH muted
    assert d.st(M.MID, 2) == 50 and d.st(M.MID_C, 4) == 0x2000 and d.st(M.MID_B, 4) == 0x8000
    c = countdown(v13, True)
    c.ram.data[:] = d.ram.data
    c.poke(M.TRANSPORT, 1); c.poke(M.MODE_BYTE, 2, 1); c.poke(SHORT_COUNTER, 0); c.poke(CLAP_COUNTER, 0)
    raised = []
    for t in range(1, 80):
        c.clear_logs()
        assert c.run(COUNTDOWN[0], set()) == STOP_LR
        for offset, value in c.c.writes: raised.append((t, 'C', offset, value))
        for offset, value in c.b.writes: raised.append((t, 'B', offset, value))
    sets = [(t, port, value) for t, port, offset, value in raised if offset == 0x18 and value not in (0x80,)]
    assert sets == [(50, 'C', 0x2000), (50, 'B', 0x8000)], sets
    releases = [t for t, port, offset, value in raised if port == 'C' and offset == 0x28 and value == 0x2000]
    assert releases == [50 + 16], releases                     # a step's 16-tick trigger
    pc7 = [t for t, port, offset, value in raised if port == 'C' and value == 0x80]
    assert pc7 == [50 + 3, 50 + 14], pc7                       # PC7 set at 17, cleared at 6, as for a step
    return 1


def check_tick_state(v13):
    m = countdown(v13, True)
    m.set_st(M.MUTEMODE, 1); m.set_st(M.MID, 9, 2); m.poke(M.TRANSPORT, 1); m.poke(M.MODE_BYTE, 2, 1)
    m.run(COUNTDOWN[0], set())
    assert m.st(M.MUTEMODE) == 1 and m.st(M.TICK, 4) == 1 and m.st(M.MID, 2) == 8 and m.st(M.RESTART) == 0
    m.poke(M.MODE_BYTE, 3, 1); m.run(COUNTDOWN[0], set())
    assert m.st(M.MUTEMODE) == 0, 'leaving Pattern Play ends the mode'
    m.set_st(M.MUTEMODE, 1); m.poke(M.MODE_BYTE, 2, 1); m.poke(M.TRANSPORT, 0); m.run(COUNTDOWN[0], set())
    assert m.st(M.MUTEMODE) == 0 and m.st(M.RESTART) == 1 and m.st(M.MID, 2) == 0, 'stopping ends the mode'


# ---------------------------------------------------------------- lights and extra-hit filter

def check_lights(v12, v13, rng):
    machines = [Machine(image, {'lights': LIGHT_LOOP, 'pop': LIGHT_POP}, v) for image, v in ((v12, False), (v13, True))]
    cases = 0
    for _ in range(200):
        mask, display, start = rng.getrandbits(16), rng.getrandbits(16), rng.getrandbits(32)
        words = []
        for mode_on in (0, 1):
            for m, v13_machine in zip(machines, (False, True)):
                m.ram.data[:] = bytes(16384)
                m.poke(LIGHT_WORD + 4, start)
                if v13_machine: m.set_st(M.MUTEMODE, mode_on); m.set_st(M.DISPLAY, display, 2)
                assert m.run(LIGHT_LOOP[0], set(), frame=(0, 0, 0, 0, 0, STOP_LR | 1),
                             r0=mask, r3=1, r6=LIGHT_WORD, r7=LED_TABLE) == STOP_LR
                words.append(m.peek(LIGHT_WORD + 4))
        def lit(bits):
            word = start
            for i in range(16):
                if bits >> i & 1: word |= int.from_bytes(v13[LED_TABLE - BASE + 4 * i:LED_TABLE - BASE + 4 * i + 4], 'little')
            return word
        assert words[0] == words[1] == lit(mask), 'mode off: the stock lights'
        assert words[3] == lit(display), 'mode on: the mode display'
        cases += 1
    return cases


def check_filter(v13, rng):
    m = Machine(v13, {}, True)
    cases = 0
    for _ in range(400):
        hits, pb2 = rng.getrandbits(9), rng.getrandbits(1)
        lenmask, hpre, mutes = rng.getrandbits(9), rng.getrandbits(9), rng.getrandbits(9)
        if rng.random() < 0.3: lenmask = hpre = mutes = 0
        m.ram.data[:] = bytes(16384)
        m.set_st(M.LENMASK, lenmask, 2); m.set_st(M.HPRE, hpre, 2); m.set_st(M.MUTES, mutes, 2)
        assert m.run(M.ADDRESS['FILTER'], {M.ANALOG_ONLY_HITS}, r0=hits, r1=pb2, r4=0x1234) == M.ANALOG_ONLY_HITS
        want = ((hits & ~lenmask) | (hpre & lenmask)) & ~mutes
        assert m.vm.regs[0] == want and m.vm.regs[1] == pb2 and m.vm.regs[4] == 0x1234
        assert m.vm.regs[14] == STOP_LR | 1, 'tail call keeps the caller\'s return address'
        cases += 1
    return cases


# ---------------------------------------------------------------- buttons

def panel_machine(image, v13):
    return Machine(image, {'panel cave': (MK.PANEL_CAVE, MK.PANEL_CAVE + len(MK.PANEL_BODY)), 'consume': CONSUME}, v13)


def panel(m, keys=None, mode=2, playing=1, busy=0, tick=None):
    for index, state in (keys or {}).items(): m.poke(KEYS + 8 * index, state, 1)
    if tick is not None: m.set_st(M.TICK, tick, 4)
    exit_pc = m.run(MK.PANEL_CAVE, {CONTINUE, CANCEL, KEEP}, r4=STATE, r5=playing, r6=busy, r7=mode,
                    r8=COMMAND, r10=AUX, r11=KEYS)
    vm = m.vm
    assert vm.regs[13] == SP_TOP and (vm.regs[4], vm.regs[8], vm.regs[10], vm.regs[11]) == (STATE, COMMAND, AUX, KEYS)
    assert (vm.regs[5], vm.regs[6], vm.regs[7]) == (playing, busy, mode)
    return exit_pc


def key(m, index): return m.peek(KEYS + 8 * index, 1)


def check_panel_unchanged(v12, v13, rng):
    a, b = panel_machine(v12, False), panel_machine(v13, True)
    cases = 0
    states = (0, 1, 3, 4, 7)
    for _ in range(3000):
        keys = {i: rng.choice(states) if rng.random() < 0.3 else 0 for i in range(21)}
        mode, playing, busy = rng.choice((2, 2, 2, 3, 1, 0)), rng.choice((1, 1, 0)), rng.choice((0, 0, 1))
        results = []
        for m in (a, b):
            m.ram.data[:] = bytes(16384)
            exit_pc = panel(m, keys, mode, playing, busy)
            results.append((exit_pc, bytes(m.ram.data)))
        (e1, r1), (e2, r2) = results
        assert e1 == e2, (keys, mode, playing, busy)
        diff = {i for i in range(16384) if r1[i] != r2[i]}
        assert diff <= ST_BYTES | STACK_BYTES, sorted(hex(0x20000000 + i) for i in diff - ST_BYTES - STACK_BYTES)
        cases += 1
    return cases


class Panel:
    """A pattern playing in Pattern Play; keys pressed and released between panel ticks."""
    def __init__(self, image):
        self.m = panel_machine(image, True)
        self.m.poke(M.PATTERN + 2, 16, 1)
        self.tick = 1000
    def run(self, advance=40, **kw):
        self.tick += advance
        return panel(self.m, tick=self.tick, **kw)
    def press(self, index, **kw): self.m.poke(KEYS + 8 * index, 3, 1); return self.run(**kw)
    def release(self, index, **kw): self.m.poke(KEYS + 8 * index, 1, 1); e = self.run(**kw); self.m.poke(KEYS + 8 * index, 0, 1); return e
    def click(self, index, gap=200, hold=200):
        self.press(index, advance=gap); return self.release(index, advance=hold)
    def st(self, offset, size=1): return self.m.st(offset, size)


def check_panel_gestures(v13):
    F, TAP, GROUP = M.KEY_FUNCTION, M.KEY_TAP, M.KEY_GROUP
    step = lambda k: M.KEY_STEP1 + k - 1
    p = Panel(v13)
    # one click arms; a second clean click within the window enters the mode on release
    assert p.press(F) == CONTINUE and key(p.m, F) == 3, 'FUNCTION is left to Scatter and the RD-6'
    assert p.release(F) == CONTINUE and p.st(M.ARMED) == 1 and p.st(M.MUTEMODE) == 0
    assert p.press(F, advance=300) == CONTINUE and p.st(M.MUTEMODE) == 0, 'nothing happens on the second press'
    assert p.release(F) == KEEP and p.st(M.MUTEMODE) == 1, 'the mode starts on the second release'
    assert p.st(M.DISPLAY, 2) == 0x00FF, 'all voices playing, no rolls'
    # in the mode: FUNCTION is handled; a double-click leaves it
    assert p.press(F, advance=500) == KEEP and key(p.m, F) == 7
    p.release(F)
    p.press(F, advance=300); assert p.release(F) == CONTINUE and p.st(M.MUTEMODE) == 0
    # too slow: no mode
    p.click(F, gap=4000); p.click(F, gap=M.WINDOW + 50)
    assert p.st(M.MUTEMODE) == 0
    # another button during either press: no mode (FUNCTION + TAP, FUNCTION + step)
    for other in (TAP, step(1), GROUP, 1):
        p.click(F, gap=4000)
        p.press(F, advance=300); p.m.poke(KEYS + 8 * other, 3, 1); p.run(); p.m.poke(KEYS + 8 * other, 0, 1)
        assert p.release(F) == CONTINUE and p.st(M.MUTEMODE) == 0, other
        p.press(F, advance=4000); p.m.poke(KEYS + 8 * other, 3, 1); p.run(); p.m.poke(KEYS + 8 * other, 0, 1)
        p.release(F); p.click(F, gap=300)
        assert p.st(M.MUTEMODE) == 0, other
    # enter the mode
    p.click(F, gap=4000); p.click(F, gap=300)
    assert p.st(M.MUTEMODE) == 1
    # steps 1-8 mute, 9-16 roll, PATTERN GROUP mutes the accent; each is handled
    for k in range(1, 9):
        assert p.press(step(k)) == KEEP and key(p.m, step(k)) == 7 and p.st(M.MUTES, 2) >> k & 1
        assert p.st(M.HELD) == step(k) and not p.st(M.DISPLAY, 2) >> (k - 1) & 1
        p.release(step(k)); assert p.st(M.HELD) == 0
    assert p.st(M.MUTES, 2) == 0x1FE and p.st(M.DISPLAY, 2) == 0
    for k in range(9, 17):
        assert p.press(step(k)) == KEEP and key(p.m, step(k)) == 7 and p.st(M.ROLLS, 2) >> (k - 8) & 1
        p.release(step(k))
    assert p.st(M.ROLLS, 2) == 0x1FE and p.st(M.DISPLAY, 2) == 0xFF00
    assert p.press(GROUP) == KEEP and key(p.m, GROUP) == 7 and p.st(M.MUTES, 2) == 0x1FF
    p.release(GROUP)
    # TAP: handled; with TAP held, 9-14 set the rate and light it, 15 and 16 clear
    assert p.press(TAP) == KEEP and key(p.m, TAP) == 7
    for rate in range(6):
        p.press(step(9 + rate)); assert p.st(M.RATE) == rate and p.st(M.DISPLAY, 2) == 1 << (8 + rate)
        p.release(step(9 + rate))
    p.press(step(2)); p.release(step(2))
    assert p.st(M.MUTES, 2) == 0x1FF and p.st(M.HELD) == 0, 'steps 1-8 do nothing with TAP held'
    p.press(step(15)); p.release(step(15)); assert p.st(M.ROLLS, 2) == 0
    p.press(step(16)); p.release(step(16)); assert p.st(M.MUTES, 2) == 0
    p.release(TAP)
    assert p.st(M.DISPLAY, 2) == 0x00FF
    # two quick presses mute two voices
    p.press(step(1)); p.press(step(2))
    assert p.st(M.MUTES, 2) == (1 << 1) | (1 << 2) and p.st(M.HELD) == step(2)
    p.release(step(2)); p.release(step(1))
    p.press(step(1)); p.release(step(1)); p.press(step(2)); p.release(step(2))
    assert p.st(M.MUTES, 2) == 0
    # holding a voice cancels its mute change and lights its length; then a step sets it
    p.press(step(3)); assert p.st(M.MUTES, 2) == 1 << 3 and p.st(M.DISPLAY, 2) == 0xFB
    p.run(advance=M.WINDOW)
    assert p.st(M.MUTES, 2) == 0 and p.st(M.DISPLAY, 2) == 0xFFFF, 'pattern length 16'
    p.press(step(5)); assert p.st(M.LEN + 3) == 5 and p.st(M.MUTES, 2) == 0 and p.st(M.DISPLAY, 2) == 0x1F
    p.release(step(5))
    p.press(step(12)); assert p.st(M.LEN + 3) == 12 and p.st(M.ROLLS, 2) == 0 and p.st(M.DISPLAY, 2) == 0xFFF
    p.release(step(12)); p.release(step(3))
    assert p.st(M.HELD) == 0 and p.st(M.DISPLAY, 2) == 0x00FF and p.st(M.MUTES, 2) == 0
    # a held voice + TAP: follows the pattern again, without a mute change
    p.press(step(3)); p.press(TAP)
    assert p.st(M.LEN + 3) == 0 and p.st(M.MUTES, 2) == 0 and key(p.m, TAP) == 7
    p.release(TAP); assert p.st(M.DISPLAY, 2) == 0xFFFF
    p.release(step(3))
    # a voice that follows the pattern shows the pattern's length
    p.m.poke(M.PATTERN + 2, 7, 1); p.press(step(8)); p.run(advance=M.WINDOW)
    assert p.st(M.DISPLAY, 2) == 0x7F and p.st(M.MUTES, 2) == 0
    p.release(step(8))
    # START/STOP is left to the RD-6
    p.press(1); assert key(p.m, 1) == 3
    p.release(1)
    # out of the mode the steps are Scatter's and the RD-6's again
    p.click(F, gap=4000); p.click(F, gap=300); assert p.st(M.MUTEMODE) == 0
    assert p.press(step(1)) == CONTINUE and key(p.m, step(1)) == 3 and p.st(M.MUTES, 2) == 0
    return 1


def check_bytes(v12, v13):
    allowed = set()
    for name, site, original, new in M.sites():
        assert v12[site - BASE:site - BASE + 4] == original and v13[site - BASE:site - BASE + 4] == new, name
        allowed |= set(range(site, site + 4))
    for name in M.ORDER:
        at, body = M.ADDRESS[name], M.BODY[name]
        assert v13[at - BASE:at - BASE + len(body)] == body and not M.check_branches(name, at, body), name
        allowed |= set(range(at, at + len(body)))
    changed = {BASE + i for i, (a, b) in enumerate(zip(v12, v13)) if a != b}
    assert changed <= allowed, sorted(hex(a) for a in changed - allowed)[:8]
    run = longest_run(v13)
    assert run >= MIN_RUN
    return len(changed), run


def main():
    rng = random.Random(1)
    stock = (HERE / 'firmware/RD-6_V1.0.5.syx').read_bytes()
    v12_syx = apply(stock, json.loads((HERE / 'source/scatter-v1.2.patch.json').read_text()))
    v13_syx = apply(stock, json.loads((HERE / 'source/scatter-v1.3.patch.json').read_text()))
    v12, v13 = bytes(decode(v12_syx, 100)[3]), bytes(decode(v13_syx)[3])
    changed, run = check_bytes(v12, v13)
    result = {
        'build': 'SCATTER_V1_3',
        'syx_sha256': hashlib.sha256(v13_syx).hexdigest(),
        'image_sha256': hashlib.sha256(v13).hexdigest(),
        'bytes_changed_from_v1_2': changed,
        'header_checksum_ok': True,
        'mask_run_blocks': run,
        'dispatcher_cases_unchanged': check_dispatcher_unchanged(v12, v13, rng),
        'countdown_cases_unchanged': check_countdown_unchanged(v12, v13),
        'light_cases': check_lights(v12, v13, rng),
        'filter_cases': check_filter(v13, rng),
        'panel_cases_unchanged': check_panel_unchanged(v12, v13, rng),
        'feature_steps': check_features(v13, rng),
    }
    check_mid_hit(v13)
    check_tick_state(v13)
    check_panel_gestures(v13)
    result['status'] = 'passed_scatter_v1_3'
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
