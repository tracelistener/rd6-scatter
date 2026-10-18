"""Check Scatter v1.2 offline; no device access.

1. It differs from Scatter v1 only at the three call sites and in the three new
   routines; the header checksum is right and the XOR mask stays recoverable
   the way the updater does it (a run of >= 100 identical blocks).
2. Step lights: the snapshot address is the one Scatter really writes, and the
   routine, run by the repo's Thumb interpreter from its real call site, returns
   the played step exactly when the snapshot is valid for the current clock step
   and pattern, the clock step otherwise, preserving r0, r3-r8 and sp.
3. Pattern Write: the panel decision (cancel, keep, or carry on) and the
   direction check are run in both v1 and v1.2 for every mode, playing, busy and
   START/STOP state. Pattern Write while playing now keeps Scatter; every other
   case decides exactly as v1 did.
Decoding stays in memory; no decrypted file is written.
"""
from pathlib import Path
import hashlib, json, re, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from apply_patch import apply
from check_fix106 import decode_syx
from rd6_thumb_machine import Program, Memory, Thumb
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from build_scatter_v1_2 import CHANGES, longest_run
import step_lights as L
import mode_keep as M
BASE = 0x08002800
HERE = Path(__file__).resolve().parents[1]
TAG = 0xD1000000
STOP_LR = 0x08001000   # outside every program region: a return lands here

def machine(image, regions):
    program = Program()
    for name, start, end in regions: program.add(name, start, image[start - BASE:end - BASE])
    memory = Memory(); memory.add('flash', BASE, image); memory.add('ram', 0x20000000, 16384, writable=True)
    return memory, Thumb(memory, program)

def check_lights(image):
    cases = 0
    for clock in range(17):
        for length in (1, 2, 3, 7, 12, 16):
            for kind in ('none', 'valid', 'other_step', 'other_length', 'bad_tag', 'bit15'):
                for source in (range(32) if kind == 'valid' else (0, 5, 15)):
                    snap = 0
                    if kind != 'none':
                        step = clock if kind != 'other_step' else (clock + 1) & 31
                        slen = length if kind != 'other_length' else (length % 16) + 1
                        snap = step | (slen << 5) | (source << 10) | TAG
                        if kind == 'bad_tag': snap ^= 0x02000000
                        if kind == 'bit15': snap |= 0x8000
                    memory, vm = machine(image, [('site', L.SITE, L.SITE + 4), ('lights', L.CAVE, L.CAVE + len(L.BODY) - 8)])
                    memory.poke(L.TRANSPORT + 8, clock, 1); memory.poke(L.PATTERN + 2, length, 1); memory.poke(L.SNAPSHOT, snap, 4)
                    sentinel = {0: 0x11111111, 3: 0x33333333, 4: 0x44444444, 5: 0x55555555, 6: 0x66666666, 7: 0x77777777, 8: L.TRANSPORT}
                    for reg, value in sentinel.items(): vm.regs[reg] = value
                    vm.regs[13] = 0x20003F00
                    assert vm.run(L.SITE, {L.SITE + 4}, 100)[0] == 'stop'
                    expected = source if kind == 'valid' and source < length else clock
                    assert vm.regs[2] == expected, (clock, length, kind, source, vm.regs[2])
                    assert all(vm.regs[r] == v for r, v in sentinel.items()) and vm.regs[13] == 0x20003F00, 'registers not preserved'
                    cases += 1
    return cases

def panel_decision(image, new, mode, playing, busy, startstop):
    # From the instruction after panel cleanup up to where v1 cancels, carries on or returns.
    regions = [('decide', M.PANEL_SITE, M.PANEL_CANCEL)]
    if new: regions = [('site', M.PANEL_SITE, M.PANEL_SITE + 4), ('rest', M.PANEL_CONTINUE, M.PANEL_CANCEL), ('cave', M.PANEL_CAVE, M.PANEL_CAVE + len(M.PANEL_BODY))]
    memory, vm = machine(image, regions)
    keys = 0x20000914
    memory.poke(keys + 8, startstop, 1)
    vm.regs[5], vm.regs[6], vm.regs[7], vm.regs[11], vm.regs[13] = playing, busy, mode, keys, 0x20003F00
    status, _ = vm.run(M.PANEL_SITE, {M.PANEL_CANCEL, M.PANEL_PROCESS, M.PANEL_KEEP}, 50)
    assert status == 'stop'
    return {M.PANEL_CANCEL: 'cancel', M.PANEL_PROCESS: 'carry on', M.PANEL_KEEP: 'keep'}[vm.regs[15]]

def direction_kept(image, new, mode, playing):
    end = M.DIRECTION_END
    regions = [('fn', M.DIRECTION_FUNCTION, end)]
    if new: regions = [('head', M.DIRECTION_FUNCTION, M.DIRECTION_SITE + 4), ('clear', M.DIRECTION_SITE + 6, end), ('cave', M.DIRECTION_CAVE, M.DIRECTION_CAVE + len(M.DIRECTION_BODY))]
    memory, vm = machine(image, regions)
    transport = 0x20000BB4
    memory.poke(transport, playing, 4); memory.poke(M.MODE, mode, 1)
    for k in range(7): memory.poke(M.DIRECTION_STATE + 4 * k, 0xA5A50000 + k, 4)
    vm.regs[0], vm.regs[14], vm.regs[13] = transport, STOP_LR | 1, 0x20003F00
    assert vm.run(M.DIRECTION_FUNCTION, {STOP_LR}, 50)[0] == 'stop'
    state = [memory.peek(M.DIRECTION_STATE + 4 * k, 4) for k in range(7)]
    if all(v == 0xA5A50000 + k for k, v in enumerate(state)): return True
    assert all(v == 0 for v in state[:6]), state
    return False

def main():
    stock = (HERE / 'firmware/RD-6_V1.0.5.syx').read_bytes()
    v1 = decode_syx(apply(stock, json.loads((HERE / 'source/scatter-v1.patch.json').read_text())))
    syx = apply(stock, json.loads((HERE / 'source/scatter-v1.2.patch.json').read_text()))
    v12 = decode_syx(syx)
    allowed = set()
    for site, _, new, cave, body in CHANGES:
        allowed |= set(range(site - BASE, site - BASE + 4)) | set(range(cave - BASE, cave - BASE + len(body)))
        assert v12[site - BASE:site - BASE + 4] == new and v12[cave - BASE:cave - BASE + len(body)] == body
    changed = {i for i, (a, b) in enumerate(zip(v1, v12)) if a != b}
    assert len(v1) == len(v12) and changed and changed <= allowed, 'unexpected bytes changed'
    frames, at = [], 0
    while at < len(syx):
        end = syx.index(0xF7, at); frames.append(syx[at:end + 1]); at = end + 1
    assert sum((frames[5][14 + k] & 0x7F) << (7 * k) for k in range(4)) == sum(v12) & 0xFFFFFFFF, 'header checksum'
    run = longest_run(v12)
    assert run >= 100, 'the updater could not recover the XOR mask'
    # The snapshot address must be the one Scatter really writes: the store in the source,
    # and the movw/movt pair Scatter v1's compiled reader uses.
    ll = (HERE / 'source/rd6_glitch_core.ll').read_text()
    assert int(re.search(r'store volatile i32 %snapshot,ptr inttoptr \(i32 (\d+) to ptr\)', ll).group(1)) == L.SNAPSHOT
    code = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(v1[0x0800B300 - BASE:L.CAVE - BASE], 0x0800B300))
    assert any(a.mnemonic == 'movw' and b.mnemonic == 'movt' and a.op_str.endswith(f'#{L.SNAPSHOT & 0xFFFF:#x}') and b.op_str.endswith(f'#{L.SNAPSHOT >> 16:#x}')
               for a, b in zip(code, code[1:])), 'Scatter v1 code does not use the snapshot address'
    light_cases = check_lights(v12)
    mode_cases = 0
    for mode in range(6):
        for playing in (0, 1):
            for busy in (0, 1):
                for startstop in (0, 3, 4):
                    old, new = panel_decision(v1, False, mode, playing, busy, startstop), panel_decision(v12, True, mode, playing, busy, startstop)
                    if mode == 3 and playing and not busy: assert new == 'keep', (mode, playing, busy, startstop, new)
                    else: assert new == old, (mode, playing, busy, startstop, old, new)
                    mode_cases += 1
            old, new = direction_kept(v1, False, mode, playing), direction_kept(v12, True, mode, playing)
            assert new == (bool(playing) and mode in (2, 3)) and (mode == 3 or new == old), (mode, playing, old, new)
            mode_cases += 1
    print(json.dumps({'status': 'passed_scatter_v1_2', 'syx_sha256': hashlib.sha256(syx).hexdigest(), 'image_sha256': hashlib.sha256(v12).hexdigest(),
                      'bytes_changed_from_v1': len(changed), 'header_checksum_ok': True, 'snapshot_address_checked': hex(L.SNAPSHOT), 'mask_run_blocks': run,
                      'step_light_cases': light_cases, 'mode_cases': mode_cases}, indent=2))

if __name__ == '__main__': main()
