"""Offline checks for the MIDI extra-hit test build on Scatter v1.3 (source/midi_extra.py).

Instruction-level: the actual bytes run in source/rd6_thumb_machine.py, which honours
PRIMASK (mrs/msr, cpsid i). Exception admission is modelled by the harness: an
interrupt is taken only while PRIMASK is clear, with the register/flag/IT context
saved and a 32-byte exception frame reserved on the stack. This models preemption,
not Cortex-M cycles or peripheral timing. No decoded firmware is saved and no
hardware is used.

1. Bytes: the build differs from Scatter v1.3 only at the four listed sites and in
   the four new routines; v1.3's routines are unchanged apart from the instruction
   pair TICK's 1/32 hook replaces; every branch, adr and table matches the listing;
   the mask stays recoverable.
2. Firmware audit (stock 1.0.5): interrupt priorities from the real NVIC set-up, the
   queue's producers and consumers, and the only cursor stores.
3. The queue: every instruction boundary of a stock enqueue preempted by Scatter's
   extra hits and by a 1/32 hit, across every wrap position; the extra-note room
   check in 20,000 cursor states; the drains preempted mid-way; the note bytes on
   the wire.
4. Scatter's extra hits: the analog filter entry for all 512 hit masks, v1.3's
   filter (mutes, own lengths) in front of it, and the TIMER14 scheduler running
   Ratchet, Roll and latched Roll, with and without mutes and own lengths, against
   Scatter v1.3 itself.
5. The regular step dispatcher with random v1.3 state, and the trigger countdown in
   every state v1.3's check uses, match Scatter v1.3 exactly (pins, RAM and the MIDI
   queue), except that a 1/32 hit now also queues its notes.
6. The 1/32 roll end to end: the stock dispatcher arms it, the countdown fires it on
   the pins and queues its notes with the step's accent; a new step or a stop
   cancels it.
With --mutations it also confirms that five deliberately broken builds each fail at
least one of these checks.
"""
from pathlib import Path
import hashlib, json, random, sys
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'source')); sys.path.insert(0, str(HERE / 'scripts'))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from apply_patch import apply
from build_scatter_v1_2 import longest_run
from build_scatter_v1_3 import decode, MIN_RUN
from build_midi_extra import build, OUT, V13
from rd6_thumb_machine import Program, Memory, Thumb
from midi_firmware_audit import graph, reach, word, control_accesses
import check_scatter_v1_3 as C
import midi_extra as M
import mute_roll as V

BASE = 0x08002800
STOP, SP, CUR, BUF = 0x08001000, 0x20003F00, 0x20000308, 0x200010A7
ROWS, NOTES = (1, 2, 3, 4, 5, 7, 8, 6), (36, 40, 45, 50, 51, 46, 42, 39)
ENQUEUE, ANALOG = (0x08002DD4, 0x08002DEC), (0x0800B560, 0x0800B580)
DRAINS = ((0x08005520, 0x08005556), (0x08005560, 0x0800559C), (0x08005638, 0x08005664), (0x0800566C, 0x0800569C))
TIMER_BODY = (0x0800BAD8, 0x0800BB1A)
COUNTDOWN = C.COUNTDOWN[0]
# 1/32 pins (GPIOC, then the cymbal's PB15) and notes, in the stock dispatcher's order
MID_VOICES = ((0x2000, 0, 36), (0x4000, 0, 40), (0x8000, 0, 45), (0x0001, 0, 50), (0, 0x8000, 51), (0x0002, 0, 46), (0x0004, 0, 42))
QUEUE_BYTES = set(range(BUF - 0x20000000, BUF - 0x20000000 + 100)) | set(range(CUR + 24 - 0x20000000, CUR + 28 - 0x20000000))
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)


def expected(hits):
    """Note bytes for a hit mask, as the stock dispatcher and rd6_output_frame order them."""
    return [n | ((hits & 1) << 7) for r, n in zip(ROWS, NOTES) if hits & (1 << r)]


def expected_mid(pins_c, pins_b, accent):
    return [n | (accent << 7) for c, b, n in MID_VOICES if pins_c & c or pins_b & b]


def midi_ranges():
    """The code, without the tables, of the new routines."""
    out = []
    for name in M.ORDER:
        instrs, _ = M.parse(M.listing(name, M.ADDRESS['SAFE']))
        code = list(md.disasm(M.BODY[name], M.ADDRESS[name], len(instrs)))
        out.append((name, (M.ADDRESS[name], code[-1].address + code[-1].size)))
    return out


def code_ranges(image, roots):
    g = graph(image, roots)
    assert not [edge for info in g.values() for edge in info[3]], 'unmodeled indirect control flow'
    addresses = sorted(set().union(*(info[0] for info in g.values())))
    ranges = []
    for at in addresses:
        ins = next(md.disasm(image[at - BASE:at - BASE + 4], at, 1))
        if ranges and at == ranges[-1][1]: ranges[-1][1] += ins.size
        else: ranges.append([at, at + ins.size])
    return ranges


def program(image, test_build=True, roots=()):
    """The queue, its drains, the analog filter, v1.3's extra-hit filter and the new code."""
    p = Program()
    ranges = [ENQUEUE, ANALOG, *DRAINS, (V.ADDRESS['FILTER'], C.code_end('FILTER'))]
    if test_build: ranges += [r for _, r in midi_ranges()]
    if roots: ranges += code_ranges(image, roots)
    for i, (a, b) in enumerate(ranges): p.add(str(i), a, image[a - BASE:b - BASE])
    return p


def machine(image, p):
    mem = Memory(); mem.add('flash', BASE, image); mem.add('ram', 0x20000000, 16384, writable=True)
    vm = Thumb(mem, p); vm.regs[13], vm.regs[14] = SP, STOP | 1
    return mem, vm


def call(vm, at, *args):
    vm.regs[:len(args)] = args
    vm.regs[13], vm.regs[14] = SP, STOP | 1
    assert vm.run(at, {STOP}, 10000)[0] == 'stop'
    return vm.regs[0]


def cursors(mem, w, on=None, off=None):
    for offset, value in ((24, w), (28, w if on is None else on), (32, w if off is None else off)):
        mem.poke(CUR + offset, value, 4)


def queued(mem, start):
    end = mem.peek(CUR + 24, 4)
    return [mem.peek(BUF + (start + i) % 100, 1) for i in range((end - start) % 100)]


class Rig(C.Machine):
    """check_scatter_v1_3's machine (GPIO ports, the dispatcher's helpers stubbed), with
    the real MIDI queue and drains instead of a logged queue call, and the new code."""
    def __init__(self, image, test_build):
        ranges = {'dispatcher': C.DISPATCHER, 'step hook': C.STEP_HOOK, 'countdown': C.COUNTDOWN,
                  'release': C.RELEASE, 'enqueue': ENQUEUE, 'analog': ANALOG}
        ranges.update({f'drain {i}': r for i, r in enumerate(DRAINS)})
        if test_build: ranges.update({'MIDI ' + name: r for name, r in midi_ranges()})
        super().__init__(image, ranges, True)
        del self.vm.intercepts[C.MIDI_QUEUE]
        self.wire = []
        self.vm.intercepts[0x08008100] = lambda vm: self.wire.append(bytes(self.peek(vm.regs[0] + i, 1) for i in range(vm.regs[1])))
        self.vm.intercepts[0x08007D24] = lambda vm: None

    def tick(self):
        """One TIMER14 trigger countdown, then the main loop's off and on drains."""
        assert self.run(COUNTDOWN, set()) == C.STOP_LR and not self.vm.primask
        for drain in (0x08005520, 0x08005560): assert self.run(drain, set()) == C.STOP_LR


# ---------------------------------------------------------------- bytes and audit

def check_bytes(v13, image):
    allowed = set()
    for site, old, new in M.sites():
        assert v13[site - BASE:site - BASE + 4] == old and image[site - BASE:site - BASE + 4] == new, hex(site)
        allowed |= set(range(site, site + 4))
    for name in M.ORDER:
        at, body = M.ADDRESS[name], M.BODY[name]
        V.SOURCE['MIDI_' + name] = M.listing(name, M.ADDRESS['SAFE'])
        assert image[at - BASE:at - BASE + len(body)] == body and not V.check_branches('MIDI_' + name, at, body), name
        allowed |= set(range(at, at + len(body)))
    changed = {BASE + i for i, (a, b) in enumerate(zip(v13, image)) if a != b}
    assert changed <= allowed, sorted(hex(a) for a in changed - allowed)[:8]
    for name in V.ORDER:
        at, body = V.ADDRESS[name], V.BODY[name]
        now = bytearray(image[at - BASE:at - BASE + len(body)])
        if name == 'TICK': now[M.MID_SITE - at:M.MID_SITE - at + 4] = bytes.fromhex('15202860')
        assert bytes(now) == body, f"v1.3's {name} changed"
    assert image[0x0800BB0A - BASE:0x0800BB0E - BASE] == v13[0x0800BB0A - BASE:0x0800BB0E - BASE], "v1.3's filter call"
    run = longest_run(image)
    assert run >= MIN_RUN
    return len(changed), run


def nvic(stock):
    p = Program()
    for a, b in ((0x080074A2, 0x080074B4), (0x08007506, 0x08007518), (0x080093EC, 0x08009466), (0x0800946C, 0x08009476)):
        p.add(hex(a), a, stock[a - BASE:b - BASE])
    mem, vm = machine(stock, p); mem.add('nvic', 0xE000E000, 4096, writable=True)
    for a, b in ((0x080074A2, 0x080074B4), (0x08007506, 0x08007518)):
        assert vm.run(a, {b}, 200)[0] == 'stop'
    assert mem.peek(0xE000ED0C, 4) & 0x700 == 0x500
    assert mem.peek(0xE000E413, 1) == 0x50 and mem.peek(0xE000E414, 1) == 0
    roots = [word(stock, BASE + 4 * i) & ~1 for i in range(1, 84) if word(stock, BASE + 4 * i) not in (0, 0x08002AAB)]
    roots += [0x080093AC]
    g = graph(stock, roots)
    producers = [r for r in roots if 0x08002DD4 in reach(g, r)]
    assert set(producers) == {0x08007628, 0x08007524, 0x080075EC, 0x080093AC}
    assert [r for r in roots if COUNTDOWN in reach(g, r)] == [0x080075EC], 'the countdown (and TICK) run in TIMER14'
    for f in (0x08005520, 0x08005560):
        assert [r for r in roots if f in reach(g, r)] == [0x080093AC]
    writes = [(a, offset) for a, kind, offset in control_accesses(stock, g) if kind == 'store' and offset in (24, 28, 32)]
    assert writes == [(0x08002DE8, 24), (0x08005548, 32), (0x0800557C, 28)], writes
    return {'TIMER13_priority': '0x50 (preempt 1, sub 1)', 'TIMER14_priority': '0x00 (preempt 0, sub 0)',
            'producer_roots': list(map(hex, producers)), 'consumer_root': '0x080093ac', 'countdown_root': '0x080075ec',
            'cursor_store_sites': [(hex(a), hex(offset)) for a, offset in writes]}


# ---------------------------------------------------------------- the queue

def capacity(image, p):
    distances = (0, 1, 2, 8, 9, 10, 11, 50, 98, 99)
    mem, vm = machine(image, p)
    cases = 0
    for w in range(100):
        for a in distances:
            for b in distances:
                for mask in (0, 1):
                    nxt = (w + 1) % 100
                    cursors(mem, w, (nxt + a) % 100, (nxt + b) % 100)
                    vm.primask = mask
                    mem.poke(BUF + w, 0xEE, 1)
                    call(vm, M.ADDRESS['SAFE'], 0xA4)
                    ok = a > 8 and b > 8
                    assert mem.peek(CUR + 24, 4) == (nxt if ok else w)
                    assert mem.peek(BUF + w, 1) == (0xA4 if ok else 0xEE)
                    assert mem.peek(CUR + 28, 4) == (nxt + a) % 100 and mem.peek(CUR + 32, 4) == (nxt + b) % 100
                    assert vm.primask == mask and vm.regs[13] == SP
                    cases += 1
    return cases


def mask_bound(image, p):
    longest = 0
    for w, on, off in ((0, 0, 0), (99, 99, 99), (0, 50, 50), (99, 10, 10), (0, 1, 1)):
        mem, vm = machine(image, p); cursors(mem, w, on, off)
        vm.regs[0] = 36; vm.regs[13], vm.regs[14], vm.regs[15] = SP, STOP | 1, M.ADDRESS['SAFE']; run = 0
        while vm.regs[15] != STOP:
            masked = vm.primask
            vm.step()
            run = run + 1 if masked else 0
            longest = max(longest, run)
            assert vm.stats['instructions'] < 100
        assert not vm.primask and vm.regs[13] == SP
    assert longest <= 40
    return longest


def interrupt(vm, entry, args, call_at=None):
    assert vm.primask == 0
    context = vm.context()
    vm.regs[13] -= 32  # hardware exception frame; the handler's stack stays below it
    if call_at: call_at(vm)
    else:
        vm.regs[:len(args)] = args; vm.regs[14] = STOP | 1
        assert vm.run(entry, {STOP}, 10000)[0] == 'stop'
    assert vm.primask == 0
    vm.restore(context)


def preempt_main(vm, mem, w, boundary, isr, main_entry=0x08002DD4, main_byte=60):
    """Run a main-context enqueue of main_byte, taking isr at the first instruction
    boundary at or after `boundary` where PRIMASK is clear."""
    cursors(mem, w)
    vm.regs[0] = main_byte; vm.regs[13], vm.regs[14], vm.regs[15] = SP, STOP | 1, main_entry
    ticks, pending, fired, masked, max_masked = 0, False, False, 0, 0
    while vm.regs[15] != STOP or not fired:
        if ticks == boundary: pending = True
        if pending and not vm.primask:
            isr(vm); pending = False; fired = True
        if vm.regs[15] == STOP:
            if not fired: pending = True; continue
            break
        vm.step(); ticks += 1
        masked = masked + 1 if vm.primask else 0
        max_masked = max(max_masked, masked)
        assert ticks < 200
    assert vm.regs[13] == SP and not vm.primask
    return max_masked


def arm_mid(m, pins_c=0xE007, pins_b=0x8000, accent=1):
    """A 1/32 hit due on the next countdown tick, as DISPATCH arms it."""
    m.poke(C.M.TRANSPORT, 1); m.poke(C.M.MODE_BYTE, 2, 1)
    m.set_st(V.MID, 1, 2); m.set_st(V.MID_C, pins_c, 4); m.set_st(V.MID_B, pins_b, 4)
    m.set_st(V.FAKE + 4, accent, 2)


def preempt(image, p):
    """A stock enqueue preempted at every instruction boundary, at every wrap position,
    by Scatter's extra hits (TIMER14 body's filter call) and by a 1/32 hit (TIMER14's
    countdown); and SAFE preempted by a stock enqueue. Nothing is lost or reordered
    inside a byte's publication."""
    cases, max_masked = 0, 0
    for w in range(100):
        for boundary in range(21):
            mem, vm = machine(image, p)
            max_masked = max(max_masked, preempt_main(vm, mem, w, boundary, lambda v: interrupt(v, 0x0800B560, (511, 1))))
            assert queued(mem, w) in ([60] + expected(511), expected(511) + [60]), (w, boundary, queued(mem, w))
            assert mem.peek(CUR + 28, 4) == w and mem.peek(CUR + 32, 4) == w
            cases += 1
    mid = expected_mid(0xE007, 0x8000, 1)
    for w in range(100):
        for boundary in range(21):
            m = Rig(image, True)
            arm_mid(m)
            def countdown_isr(vm):
                interrupt(vm, None, (), call_at=lambda v: (v.regs.__setitem__(14, STOP | 1),
                                                           v.run(COUNTDOWN, {STOP}, 10000)))
            max_masked = max(max_masked, preempt_main(m.vm, m.memory, w, boundary, countdown_isr))
            assert queued(m.memory, w) in ([60] + mid, mid + [60]), (w, boundary, queued(m.memory, w))
            assert m.st(V.MID, 2) == 0
            cases += 1
    # The extra-note room check also stays protected if a stock interrupt arrives.
    for boundary in range(65):
        mem, vm = machine(image, p)
        preempt_main(vm, mem, 99, boundary, lambda v: interrupt(v, 0x08002DD4, (60,)),
                     main_entry=M.ADDRESS['SAFE'], main_byte=0xA4)
        assert sorted(queued(mem, 99)) == [60, 0xA4]
        cases += 1
    return cases, max_masked


def consumers(image, p):
    mem, vm = machine(image, p); messages = []
    vm.intercepts[0x08008100] = lambda v: messages.append(bytes(mem.peek(v.regs[0] + i, 1) for i in range(v.regs[1])))
    vm.intercepts[0x08007D24] = lambda v: None
    mem.poke(0x20000304, 3, 1)
    call(vm, 0x0800B560, 511, 0)
    call(vm, 0x08005560)
    assert messages == [bytes((0x93, n, 0x70)) for n in NOTES]
    for i in range(4):
        call(vm, 0x08005520)
        assert len(messages) == 8
    call(vm, 0x08005520)
    assert messages[8:] == [bytes((0x83, n, 0x40)) for n in NOTES]
    assert mem.peek(CUR + 24, 4) == mem.peek(CUR + 28, 4) == mem.peek(CUR + 32, 4) == 8
    # The note-on consumer resets one global countdown for all pending offs.
    call(vm, 0x0800B560, 2, 0); call(vm, 0x08005560)
    assert messages[-1] == bytes((0x93, 36, 0x50))
    for _ in range(5): call(vm, 0x08005520)
    assert messages[-1] == bytes((0x83, 36, 0x40))
    return len(messages)


def consumer_preemption(image, p):
    cases = 0
    for entry in (0x08005520, 0x08005560):
        for boundary in range(80):
            mem, vm = machine(image, p); wire = []
            vm.intercepts[0x08007D24] = lambda v: None
            vm.intercepts[0x08008100] = lambda v: wire.append(bytes(mem.peek(v.regs[0] + i, 1) for i in range(v.regs[1])))
            call(vm, 0x08002DD4, 36)
            if entry == 0x08005520:
                call(vm, 0x08005560); mem.poke(CUR + 36, 1, 4)
            vm.regs[13], vm.regs[14], vm.regs[15] = SP, STOP | 1, entry
            ticks = 0; fired = False
            while vm.regs[15] != STOP or not fired:
                if ticks >= boundary and not fired:
                    interrupt(vm, 0x0800B560, (511, 0)); fired = True
                if vm.regs[15] == STOP:
                    if not fired: ticks = boundary; continue
                    break
                vm.step(); ticks += 1
                assert ticks < 2000
            # The new off boundary excludes bytes appended before their ons.
            # Every later on must get a final off, with all cursors drained.
            call(vm, 0x08005560)
            for _ in range(5): call(vm, 0x08005520)
            assert sum(m[0] == 0x90 for m in wire) == 9
            assert all(next(m[0] for m in reversed(wire) if m[1] == n) == 0x80 for n in NOTES)
            assert mem.peek(CUR + 24, 4) == mem.peek(CUR + 28, 4) == mem.peek(CUR + 32, 4) == 9
            assert vm.regs[13] == SP and not vm.primask
            cases += 1
    return cases


# ---------------------------------------------------------------- Scatter's extra hits

def filters(v13, image, p):
    """The analog filter entry: all 512 masks with both PB2 states, against v1.3's filter."""
    oldp = Program(); oldp.add('filter', 0x0800B560, v13[0x0800B560 - BASE:0x0800B580 - BASE])
    for hits in range(512):
        for pb2 in (0, 1):
            mem, vm = machine(image, p); om, ov = machine(v13, oldp)
            regs = [0xAA000000 + i for i in range(4, 13)]
            vm.regs[4:13] = regs
            result = call(vm, 0x0800B560, hits, pb2)
            assert result == call(ov, 0x0800B560, hits, pb2)
            assert queued(mem, 0) == expected(hits)
            assert vm.regs[4:13] == regs and vm.regs[13] == SP and vm.primask == 0
    return 1024


def v13_filter(v13, image, p, rng):
    """v1.3's extra-hit filter in front: muted voices send nothing, voices with their own
    length send this step's hit, and the analog result is v1.3's."""
    old = program(v13, test_build=False)
    cases = 0
    for _ in range(400):
        hits, pb2 = rng.getrandbits(9), rng.getrandbits(1)
        lenmask, hpre, mutes = rng.getrandbits(9), rng.getrandbits(9), rng.getrandbits(9)
        if rng.random() < 0.3: lenmask = hpre = mutes = 0
        results = []
        for image_, p_ in ((v13, old), (image, p)):
            mem, vm = machine(image_, p_)
            for offset, value in ((V.LENMASK, lenmask), (V.HPRE, hpre), (V.MUTES, mutes)): mem.poke(V.ST + offset, value, 2)
            regs = [0xAA000000 + i for i in range(4, 12)]
            vm.regs[4:12] = regs
            result = call(vm, V.ADDRESS['FILTER'], hits, pb2)
            assert vm.regs[4:12] == regs and vm.regs[13] == SP and vm.primask == 0
            results.append((result, vm.regs[12]))   # v1.3's filter uses ip as scratch
        assert results[0] == results[1]
        assert queued(mem, 0) == expected(((hits & ~lenmask) | (hpre & lenmask)) & ~mutes)
        cases += 1
    return cases


def scheduler(v13, image, p_new):
    """TIMER14's body with Scatter's effects as the hardware runs them, for v1.3 and the
    test build side by side: the same repeats reach the analog emitter, and the test
    build's repeats reach MIDI out, after v1.3's mutes and own lengths."""
    totals, cases = {}, 0
    rigs = []
    for image_, test_build in ((v13, False), (image, True)):
        p = program(image_, test_build, [0x0800B844])
        p.add('timer body', TIMER_BODY[0], image_[TIMER_BODY[0] - BASE:TIMER_BODY[1] - BASE])
        rigs.append((image_, p))
    states = ((0, 0, 0), (1 << 1 | 1 << 6 | 1, 0, 0), (0, 1 << 2 | 1 << 3, 1 << 2), (1 << 8, 1 << 4, 0))
    for mode, depth, latch in ((0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0), (4, 1, 0), (4, 4, 0),
                               (5, 4, 0), (6, 4, 0), (5, 4, 1), (6, 4, 1)):
        for mutes, lenmask, hpre in states:
            runs = []
            for image_, p in rigs:
                mem, vm = machine(image_, p)
                mem.add('GPIOB input', 0x48000410, 4)
                cmd = (1 << 16) | (depth << 13) | (mode << 10) | (16 << 5)
                mem.poke(0x20002000, 0xD6A5B000 | (mode * 4 + depth - 1), 4)
                mem.poke(0x20002030, latch, 4)
                mem.poke(0x20002004, cmd, 4)
                state = (0, 480, 0, (4 if depth == 4 else 2) if mode == 4 else 1, 1, 18, 0, 16, cmd)
                for i, value in enumerate(state): mem.poke(0x20002008 + 4 * i, value, 4)
                mem.poke(0x2000205C, 511, 4)
                mem.poke(0x20000260, 2, 1); mem.poke(0x20000BB4, 1, 4)
                mem.poke(0x20000A9E, 16, 1)
                for row in range(9): mem.poke(0x20000AA0 + row * 2, 65535, 2)
                for offset, value in ((V.MUTES, mutes), (V.LENMASK, lenmask), (V.HPRE, hpre)): mem.poke(V.ST + offset, value, 2)
                emitted, analog, wire = [], [], []
                tick = 0
                vm.observers[0x0800B560] = [lambda v: emitted.append((tick, v.regs[0]))]
                vm.intercepts[0x0800BABC] = lambda v: analog.append((tick, v.regs[0]))
                vm.intercepts[0x08007D24] = lambda v: None
                vm.intercepts[0x08008100] = lambda v, mem=mem: wire.append((tick, bytes(mem.peek(v.regs[0] + i, 1) for i in range(v.regs[1]))))
                for tick in range(1, 601):
                    call(vm, TIMER_BODY[0], 0x20002008, 0x20002004)
                    # The stock loop's off-before-on order, once per timer tick.
                    call(vm, 0x08005520); call(vm, 0x08005560)
                    assert not vm.primask
                # A stop cancels pending repeats without adding MIDI bytes.
                mem.poke(0x20000BB4, 0, 4)
                before = mem.peek(CUR + 24, 4)
                for _ in range(20): call(vm, TIMER_BODY[0], 0x20002008, 0x20002004)
                assert mem.peek(CUR + 24, 4) == before
                runs.append((emitted, analog, wire))
            (e13, a13, w13), (e, a, w) = runs
            due = {0: [], 1: [], 2: [], 3: [], 4: ([240] if depth == 1 else [120, 240, 360]),
                   5: [240, 480], 6: [160, 320, 480]}[mode]
            filtered = ((511 & ~lenmask) | (hpre & lenmask)) & ~mutes
            assert e == e13 and [t for t, _ in e] == due and all(h == filtered for _, h in e), (mode, depth, e)
            assert a == a13, 'the analog repeats are v1.3\'s'
            assert w13 == [], 'v1.3 sends no repeats on MIDI'
            ons = [m for _, m in w if m[0] & 0xF0 == 0x90]
            offs = [m for _, m in w if m[0] & 0xF0 == 0x80]
            assert ons == [bytes((0x90, n & 0x7F, 0x70 if n & 0x80 else 0x50)) for _ in due for n in expected(filtered)], (mode, depth, ons)
            assert offs == [bytes((0x80, n & 0x7F, 0x40)) for _ in due for n in expected(filtered)]
            assert [t for t, m in w if m[0] & 0xF0 == 0x90][::max(1, len(expected(filtered)))] == due, 'notes go out on the repeat tick'
            if (mutes, lenmask, hpre) == (0, 0, 0):
                assert [h for _, h in a] == [511 & ~64] * len(due), 'the analog filter keeps its clap limitation'
                totals[f'mode_{mode}_depth_{depth}_latch_{latch}'] = due
            cases += 1
    return totals, cases


# ---------------------------------------------------------------- unchanged paths

def random_v13_state(m, rng):
    for lane in range(1, 9): m.set_st(V.LEN + lane, rng.choice((0, 0, rng.randint(1, 16))))
    m.set_st(V.RATE, rng.randrange(6)); m.set_st(V.ROLLS, rng.getrandbits(8) << 1, 2)
    m.set_st(V.MUTES, rng.getrandbits(9) if rng.random() < 0.6 else 0, 2)
    m.set_st(V.RESTART, rng.random() < 0.2); m.set_st(V.N, rng.randrange(1000), 4)
    m.set_st(V.LAST, rng.getrandbits(16), 4); m.set_st(V.TICK, rng.getrandbits(16) + 0x10000, 4)


def unchanged_steps(v13, image, rng):
    """The regular step dispatcher, entered at the top and run through v1.3's DISPATCH
    with the real queue: identical pins, helper calls and RAM (queue included)."""
    a, b = Rig(v13, False), Rig(image, True)
    cases = 0
    for case in range(600):
        rows = [rng.getrandbits(16) for _ in range(9)]
        length = rng.randint(1, 16); s = rng.randrange(length)
        mask = rng.choice((0, 1 << s, 1 << rng.randrange(16)))
        state = rng.getstate(); w = rng.randrange(100)
        for m in (a, b):
            m.ram.data[:] = bytes(16384)
            rng.setstate(state); w = rng.randrange(100)
            if case % 3: random_v13_state(m, rng)
            cursors(m.memory, w)
            C.setup_step(m, rows, length, s, mask)
        results = [C.step(m) for m in (a, b)]
        assert results[0] == results[1], case
        assert not b.vm.primask
        r1, r2 = bytes(a.ram.data), bytes(b.ram.data)
        diff = {i for i in range(16384) if r1[i] != r2[i]}
        assert diff <= C.STACK_BYTES, sorted(hex(0x20000000 + i) for i in diff - C.STACK_BYTES)
        cases += 1
    return cases


def unchanged_countdown(v13, image, rng):
    """The trigger countdown in every state v1.3's check uses, with and without a 1/32
    hit pending: identical pins, registers and RAM, except that a 1/32 hit firing now
    also queues its notes."""
    a, b = Rig(v13, False), Rig(image, True)
    cases = fired = 0
    pins = [(c | 0, bb) for c, bb in ((0x2000, 0), (0xE007, 0x8000), (0, 0x8000), (0x0006, 0), (0x4001, 0x8000))]
    for short in (0, 1, 2, 3, 4, 5, 6, 7, 16, 17, 18, 19, 20, 21):
        for clap in (0, 1, 10, 11, 109, 110, 111, 120, 121, 220, 221, 230, 231, 330, 331, 339, 340):
            for flag in (0, 1):
                for playing, mode in ((1, 2), (0, 2), (1, 3)):
                    mid = rng.choice((0, 0, 1, 2))
                    (pc, pb), accent, w = rng.choice(pins), rng.getrandbits(1), rng.randrange(100)
                    results = []
                    for m in (a, b):
                        m.ram.data[:] = bytes(16384); m.clear_logs()
                        m.poke(C.SHORT_COUNTER, short); m.poke(C.CLAP_COUNTER, clap); m.poke(0x200011A4, 1)
                        m.poke(V.SHORT_FLAG, flag); m.poke(V.TRANSPORT, playing); m.poke(V.MODE_BYTE, mode, 1)
                        m.set_st(V.MID, mid, 2); m.set_st(V.MID_C, pc, 4); m.set_st(V.MID_B, pb, 4); m.set_st(V.FAKE + 4, accent, 2)
                        cursors(m.memory, w)
                        m.c.octl, m.b.octl = 0xE387, 0x8000
                        assert m.run(COUNTDOWN, set(), r1=0x1111, r3=0x3333, r7=0x7777, r8=0x8888, r12=0xCCCC) == C.STOP_LR
                        results.append((bytes(m.ram.data), list(m.c.writes), list(m.b.writes), list(m.vm.regs[:13]), m.vm.primask))
                    (r1, c1, b1, g1, _), (r2, c2, b2, g2, primask) = results
                    assert (c1, b1, g1) == (c2, b2, g2) and not primask, (short, clap, flag, playing, mid)
                    fires = playing and mid == 1
                    diff = {i for i in range(16384) if r1[i] != r2[i]}
                    assert diff <= C.STACK_BYTES | (QUEUE_BYTES if fires else set()), sorted(hex(0x20000000 + i) for i in diff)
                    assert queued(b.memory, w) == (expected_mid(pc, pb, accent) if fires else [])
                    assert queued(a.memory, w) == []
                    fired += fires; cases += 1
    return cases, fired


# ---------------------------------------------------------------- the 1/32 roll end to end

def mid_end_to_end(image):
    """As check_scatter_v1_3's 1/32 check, on the test build with the real queue: BD, CY
    and CP rolled at 1/32 with OH muted and an accented second step. Each step plays BD,
    CY and CP through the stock dispatcher; half a step later the second hit fires on
    BD's and CY's pins and queues BD and CY with the step's accent."""
    m = Rig(image, True)
    m.poke(0x20000304, 0, 1)
    m.set_st(V.RATE, 1); m.set_st(V.ROLLS, (1 << 1) | (1 << 5) | (1 << 6) | (1 << 7), 2); m.set_st(V.MUTES, 1 << 7, 2)
    rows = [0] * 9; rows[0] = 1 << 1               # accent on step 1 (the second step)
    for n, tick in enumerate((1000, 1100)):
        m.set_st(V.TICK, tick, 4)
        C.setup_step(m, rows, 16, n, 1 << n)
        fired, *_ = C.step(m)
        assert fired == (1 << 1) | (1 << 5) | (1 << 6) | (n == 1)
    step_notes = [0x24, 0x33, 0x27] + [0xA4, 0xB3, 0xA7]
    assert queued(m.memory, 0) == step_notes and m.st(V.MID, 2) == 50
    m.set_st(V.TICK, 1100, 4)
    m.wire.clear(); pins = []
    m.poke(C.SHORT_COUNTER, 0); m.poke(C.CLAP_COUNTER, 0)
    for t in range(1, 80):
        m.clear_logs()
        m.tick()
        pins += [(t, 'C', v) for o, v in m.c.writes if o == 0x18 and v != 0x80] + [(t, 'B', v) for o, v in m.b.writes if o == 0x18]
        if t == 49: assert queued(m.memory, 0) == step_notes
        if t == 50: assert queued(m.memory, 0) == step_notes + [0xA4, 0xB3]
    assert pins == [(50, 'C', 0x2000), (50, 'B', 0x8000)], pins
    ons = [msg for msg in m.wire if msg[0] == 0x90]
    assert ons == [bytes((0x90, n & 0x7F, 0x50)) for n in step_notes[:3]] + [bytes((0x90, n & 0x7F, 0x70)) for n in step_notes[3:]] + \
        [bytes((0x90, 0x24, 0x70)), bytes((0x90, 0x33, 0x70))], ons
    assert [msg[1] for msg in m.wire if msg[0] == 0x80][-2:] == [0x24, 0x33], 'the second hit gets its note-offs'
    # A new step before the second hit, or a stop, cancels it and its notes.
    for cancel in ('step', 'stop'):
        m.ram.data[:] = bytes(16384)
        m.set_st(V.RATE, 1); m.set_st(V.ROLLS, 1 << 1, 2)
        for n, tick in enumerate((1000, 1100)):
            m.set_st(V.TICK, tick, 4); C.setup_step(m, [0] * 9, 16, n, 1 << n); C.step(m)
        assert m.st(V.MID, 2) == 50
        if cancel == 'step':
            m.set_st(V.TICK, 1110, 4); C.setup_step(m, [0] * 9, 16, 2, 1 << 2); C.step(m)
            m.set_st(V.ROLLS, 0, 2); C.setup_step(m, [0] * 9, 16, 3, 1 << 3); C.step(m)
        else:
            m.poke(V.TRANSPORT, 0)
        before = queued(m.memory, 0)
        for t in range(1, 80): m.tick()
        assert queued(m.memory, 0) == before and m.st(V.MID, 2) == 0, cancel
    return 1


def mutations(v13, image):
    """Each of these faults must make at least one check fail (run with --mutations)."""
    def mutant(address, old, new):
        out = bytearray(image); i = address - BASE
        assert out[i:i + len(old)] == old, hex(address)
        out[i:i + len(old)] = new
        return bytes(out)
    mid, body = M.ADDRESS['MID'], M.BODY['MID']
    accent = body.index(bytes.fromhex('07f00107'))           # and r7, r7, #1
    queue = body.index(bytes.fromhex('fff7a8ff'))            # bl SAFE
    cpsid = M.ADDRESS['STOCK'] + M.BODY['STOCK'].index(bytes.fromhex('72b6'))
    cases = {
        'MID drops the accent': mutant(mid + accent, bytes.fromhex('07f00107'), bytes.fromhex('07f00007')),
        'MID queues nothing': mutant(mid + queue, bytes.fromhex('fff7a8ff'), bytes.fromhex('00bf00bf')),
        'no 1/32 hook': mutant(M.MID_SITE, image[M.MID_SITE - BASE:M.MID_SITE - BASE + 4], bytes.fromhex('15202860')),
        'STOCK does not mask interrupts': mutant(cpsid, bytes.fromhex('72b6'), bytes.fromhex('00bf')),
        'off drain stops at the write cursor': mutant(0x08005534, bytes.fromhex('e169'), bytes.fromhex('a169')),
    }
    caught = {}
    for name, bad in cases.items():
        caught[name] = []
        for check in (lambda: unchanged_countdown(v13, bad, random.Random(5)), lambda: mid_end_to_end(bad),
                      lambda: preempt(bad, program(bad)), lambda: consumer_preemption(bad, program(bad))):
            try: check()
            except Exception: caught[name].append(check.__code__.co_names[0])
        assert caught[name], f'{name} passed every check'
    return caught


def main():
    rng = random.Random(1313)
    stock = (HERE / 'firmware/RD-6_V1.0.5.syx').read_bytes()
    v13 = bytes(decode(apply(stock, json.loads(V13.read_text())))[3])
    syx, image = build(stock)
    assert apply(stock, json.loads(OUT.read_text())) == syx, 'the published patch is the build'
    changed, run = check_bytes(v13, image)
    p = program(image)
    report = {
        'build': 'SCATTER_V1_3_MIDI_TEST',
        'syx_sha256': hashlib.sha256(syx).hexdigest(),
        'image_sha256': hashlib.sha256(image).hexdigest(),
        'bytes_changed_from_v1_3': changed,
        'mask_run_blocks': run,
        'firmware_audit': nvic(decode(stock, 100)[3]),
        'capacity_cases': capacity(image, p),
        'max_extra_enqueue_masked_instructions': mask_bound(image, p),
        'preemption_cases_and_max_stock_masked_instructions': preempt(image, p),
        'wire_messages': consumers(image, p),
        'consumer_preemption_cases': consumer_preemption(image, p),
        'filter_cases': filters(v13, image, p),
        'v1_3_filter_cases': v13_filter(v13, image, p, rng),
        'scheduler_extra_hit_ticks_and_cases': scheduler(v13, image, p),
        'dispatcher_cases_unchanged': unchanged_steps(v13, image, rng),
        'countdown_cases_and_1_32_hits': unchanged_countdown(v13, image, rng),
        'mid_end_to_end': mid_end_to_end(image),
    }
    if '--mutations' in sys.argv: report['mutations_caught_by'] = mutations(v13, image)
    report.update(hardware_tested=False, status='passed_scatter_v1_3_midi_test')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
