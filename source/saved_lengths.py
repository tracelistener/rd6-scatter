"""Scatter v1.4.1: the MIDI extra-hit build, plus each voice's loop length (v1.3's length
per voice) saved with its pattern in the RD-6's EEPROM and shown in Pattern Write, and a
length view that stays after you let go, so a voice can take its own button's length.

How the stock 1.0.5 firmware keeps patterns (traced in source/check_saved_lengths.py):
- The EEPROM is a 32 KB I2C part (device 0xA0), driven by bit-banged code with no lock.
  eeprom_read(address, buffer, length) is 0x0800381C and eeprom_write is 0x0800383A,
  which waits 5 ms after each write.
- Pattern p of group g lives in a 64-byte slot at (16 g + p) * 64. Every stock read and
  write of a slot covers its first 22 bytes only: the pattern (4 header bytes, then nine
  16-bit rows). Bytes 22-63 of each slot are never read or written. Songs are at 0x1000,
  settings at 0x3000 and 0x3080.
- 0x08003630 loads the playing pattern (0x20000A9C) when its slot changes, remembering
  the slot's address at 0x20000288. It runs from the main loop, and from TIMER2, TIMER13
  and TIMER14 at Start and at the end of a pattern.
- The main loop saves edits from 0x080072E4 when a timer asks for a save (every half
  second or so): the playing pattern, then the song. Each write is read back and any byte
  that differs is written again, because a timer's pattern load can cut into it.

The lengths go in bytes 22-31 of the pattern's own slot: a tag, the 8 lengths (BD..CH,
0 = follow the pattern, 1-16 steps) and a check byte (the low byte of the inverted sum
of the other 9). A slot whose bytes don't form such a record has no saved lengths.

- BOOT, after the last start-up call (0x080093A0), reads all 32 records into a copy in
  RAM (CACHE, 8 bytes a slot) and gives the loaded pattern its lengths. Nothing plays yet.
- LOAD, in 0x08003630 in place of its call to the pattern tidy-up (0x08005B70), copies
  the new pattern's 8 lengths from CACHE to v1.3's LEN. It touches only RAM, so it is
  safe in the timers. Before BOOT has filled CACHE it does nothing.
- SET, in v1.3's set_length (PANEL, main loop) in place of its LEN store, also stores the
  length in CACHE for the playing pattern's slot and marks the slot to save. Interrupts
  are masked across both stores, so a pattern load can't come between them.
- SAVE, in 0x080072E4 in place of its call to the song save (0x08003760), runs after the
  stock saves: it writes one marked slot's record, reads it back, and if it differs marks
  the slot again, up to 3 times in a row.

- SHOW, in the light builder in place of its call to v1.2's step routine (0x080064EA), runs
  while a pattern plays. In Pattern Write, when the selected voice has its own length L, the
  running light shows the step that voice last played, (steps since Start - 1) mod L, and
  its steps past L stay dark, because they don't play. Everything else is v1.2's.

The length view (v1.4.1). In v1.3 a voice's length is set by holding its button (1-8) and
pressing a step, so a voice could never take its own button's length, and letting go
closed the view. Now, if the length was on show and none was set during the hold, the view
stays after the button is let go (LATCHED) for TIMEOUT ticks (about 2 s): a step press,
the voice's own button included, sets the length and TAP makes the voice follow the
pattern, through v1.3's own hit and TAP paths, since HELD still names the voice. The view
then shows the new length and stays for another TIMEOUT after each press, as it stays
while the button is held.
- LATCH, at the let-go check in PANEL's p_mode (0x0800D08E), keeps HELD when the button is
  let go with the length on show and none chosen, closes the view after TIMEOUT, and
  otherwise does what v1.3 did.
- NEWHOLD, in PANEL's p_plain in place of its HELD store (0x0800D11E), starts each hold
  with nothing chosen and the view not latched.
- SET also marks the hold as chosen (CHOSEN) and restarts a latched view's TIMEOUT.

Mutes, rolls and the roll rate are not saved. RAM: LATCHED, CHOSEN, LATCH_T, LOADED, FAILS,
DIRTY and CACHE follow v1.3's state at ST (0x20002100); v1.2's start-up clear of
0x20002000 grows from 0x158 to 0x268 bytes, so they start at zero. The code follows the
MIDI routines, from 0x0800D300.
"""
import re
import mute_roll as V
from mute_roll import branch, parse

ST = V.ST
LATCHED = 0x58      # u8   the length view stays after the voice's button was let go
CHOSEN = 0x59       # u8   a length was set during this hold
LATCH_T = 0x5C      # u32  tick when the view latched
TIMEOUT = 5 * V.WINDOW      # TIMER14 ticks a latched view stays, about 2 s
LATCH_SITE = 0x0800D08E     # PANEL p_mode: add.w r0, fp, r6, lsl #3 (the let-go check)
SCAN_START = 0x0800D09E     # PANEL p_scan_start
HOLD_SITE = 0x0800D11E      # PANEL p_plain: strb.w r3, [r7, #HELD]
LOADED = 0x60       # u8   CACHE holds the EEPROM's records
FAILS = 0x61        # u8   failed saves in a row
DIRTY = 0x64        # u32  slots to save, bit n = slot n
CACHE = 0x68        # u8[32][8] lengths per slot, BD..CH
END = 0x168
TAG = 0x53
RECORD = 22         # the record's offset in its 64-byte slot
RECORD_LEN = 10
SLOT_ADDRESS = 0x20000288   # u16 EEPROM address of the slot in the playing pattern
EEPROM_READ, EEPROM_WRITE = 0x0800381C, 0x0800383A
TIDY = 0x08005B70           # stock tidy-up of a loaded pattern
SONG_SAVE = 0x08003760      # stock song save, called after the pattern save
LAST_INIT = 0x08004E9C      # the last start-up call before the main loop
# Pattern Write's step lights (light builder 0x0800641C, main loop, playing): the selected voice's
# row, with the running light from v1.2's step routine, called at 0x080064EA.
LIGHT_SITE = 0x080064EA
STEP_LIGHT = 0x0800CD90     # v1.2: r2 = the step the running light shows
SCALE_SHOWN = 0x20000230    # nonzero: Pattern Write's lights show the scale instead
SELECTED_ROW = 0x20000364   # address of the selected voice's row in the playing pattern
ROW0 = 0x20000AA0           # the playing pattern's first row (accent)

_F = dict(ST_LO=ST & 0xFFFF, ST_HI=ST >> 16, LEN=V.LEN, LEN1=V.LEN + 1, LOADED=LOADED, FAILS=FAILS,
          DIRTY=DIRTY, CACHE=CACHE, CACHE_1=CACHE - 1, TAG=TAG, RECORD=RECORD, RECORD_LEN=RECORD_LEN,
          SLOT_LO=SLOT_ADDRESS & 0xFFFF, EEPROM_READ=EEPROM_READ, EEPROM_WRITE=EEPROM_WRITE, TIDY=TIDY,
          SONG_SAVE=SONG_SAVE, LAST_INIT=LAST_INIT, STEP_LIGHT=STEP_LIGHT, MODE_LO=V.MODE_BYTE & 0xFFFF,
          SCALE_LO=SCALE_SHOWN & 0xFFFF, ROW_PTR_LO=SELECTED_ROW & 0xFFFF, ROW0_LO=ROW0 & 0xFFFF, N=V.N,
          LATCHED=LATCHED, CHOSEN=CHOSEN, LATCH_T=LATCH_T, TIMEOUT=TIMEOUT, SCAN_START=SCAN_START,
          HELD=V.HELD, HELD_T=V.HELD_T, TICK=V.TICK, WINDOW=V.WINDOW)

SOURCE = {}
SOURCE['APPLY'] = """
apply:                                @ r0 = a slot's EEPROM address, r4 = ST: its lengths to LEN
    tst    r0, #0x3f
    bne    a_done
    cmp.w  r0, #0x800
    bhs    a_done
    add.w  r0, r4, r0, lsr #3
    add.w  r0, r0, #{CACHE}
    add.w  r1, r4, #{LEN1}
    movs   r2, #0
a_copy:
    ldrb   r3, [r0, r2]
    strb   r3, [r1, r2]
    adds   r2, #1
    cmp    r2, #8
    blo    a_copy
a_done:
    bx     lr
"""
SOURCE['LOAD'] = """
load:                                 @ the playing pattern was just read from its slot
    push   {{r4, lr}}
    bl     {TIDY}                     @ the replaced call
    movw   r4, #{ST_LO}
    movt   r4, #{ST_HI}
    ldrb.w r0, [r4, #{LOADED}]
    cbz    r0, l_done
    movw   r0, #{SLOT_LO}
    movt   r0, #0x2000
    ldrh   r0, [r0]
    bl     APPLY_ADDRESS
l_done:
    pop    {{r4, pc}}
"""
SOURCE['SET'] = """
set:                                  @ from set_length: r0 = ST + row (1-8), r1 = length, r7 = ST
    push   {{r2, r3}}                 @ PANEL passes r3, the key, on to rd6_panel_consume
    mrs    r3, primask
    cpsid  i
    strb.w r1, [r0, #{LEN}]           @ the replaced instruction
    ldrb.w r2, [r7, #{LOADED}]
    cbz    r2, s_done
    movw   r2, #{SLOT_LO}
    movt   r2, #0x2000
    ldrh   r2, [r2]
    tst    r2, #0x3f
    bne    s_done
    cmp.w  r2, #0x800
    bhs    s_done
    subs   r0, r0, r7
    add.w  r0, r0, r2, lsr #3
    add    r0, r7
    strb.w r1, [r0, #{CACHE_1}]       @ CACHE[slot][row - 1]
    lsrs   r2, r2, #6
    movs   r0, #1
    lsls   r0, r2
    ldr.w  r2, [r7, #{DIRTY}]
    orrs   r2, r0
    str.w  r2, [r7, #{DIRTY}]
    movs   r0, #0
    strb.w r0, [r7, #{FAILS}]
s_done:
    movs   r0, #1                     @ a length was chosen in this hold
    strb.w r0, [r7, #{CHOSEN}]
    ldrb.w r0, [r7, #{LATCHED}]       @ a latched view shows the new length for another TIMEOUT
    cbz    r0, s_out
    ldr    r0, [r7, #{TICK}]
    str.w  r0, [r7, #{LATCH_T}]
s_out:
    msr    primask, r3
    pop    {{r2, r3}}
    bx     lr
"""
SOURCE['SAVE'] = """
save:                                 @ the main loop's save, after the stock pattern save
    push   {{r4, r5, r6, r7, lr}}
    sub    sp, #28
    bl     {SONG_SAVE}                @ the replaced call
    movw   r4, #{ST_LO}
    movt   r4, #{ST_HI}
    ldrb.w r0, [r4, #{LOADED}]
    cmp    r0, #0
    beq    v_done
    ldr.w  r0, [r4, #{DIRTY}]
    movs   r5, #0
v_find:                               @ r5 = the lowest marked slot
    lsr.w  r1, r0, r5
    lsls   r1, r1, #31
    bne    v_take
    adds   r5, #1
    cmp    r5, #32
    blo    v_find
    b      v_done
v_take:
    movs   r1, #1
    lsls   r1, r5
    bics   r0, r1
    str.w  r0, [r4, #{DIRTY}]
    add.w  r1, r4, #{CACHE}           @ the record: tag, 8 lengths, check
    add.w  r1, r1, r5, lsl #3
    mov    r7, sp
    movs   r2, #{TAG}
    strb   r2, [r7]
    movs   r0, #0
v_copy:
    ldrb   r3, [r1, r0]
    adds   r0, #1
    strb   r3, [r7, r0]
    add    r2, r3
    cmp    r0, #8
    blo    v_copy
    mvns   r2, r2
    strb   r2, [r7, #9]
    lsls   r0, r5, #6                 @ write it after the slot's 22 pattern bytes
    adds   r0, #{RECORD}
    mov    r1, r7
    movs   r2, #{RECORD_LEN}
    bl     {EEPROM_WRITE}
    lsls   r0, r5, #6                 @ and read it back
    adds   r0, #{RECORD}
    add.w  r1, r7, #12
    movs   r2, #{RECORD_LEN}
    bl     {EEPROM_READ}
    movs   r0, #0
v_cmp:
    ldrb   r1, [r7, r0]
    adds   r2, r7, r0
    ldrb   r2, [r2, #12]
    cmp    r1, r2
    bne    v_fail
    adds   r0, #1
    cmp    r0, #{RECORD_LEN}
    blo    v_cmp
    movs   r0, #0
    strb.w r0, [r4, #{FAILS}]
    b      v_done
v_fail:
    ldrb.w r0, [r4, #{FAILS}]         @ mark it again, at most 3 times in a row
    cmp    r0, #3
    bhs    v_give_up
    adds   r0, #1
    strb.w r0, [r4, #{FAILS}]
    movs   r1, #1
    lsls   r1, r5
    ldr.w  r0, [r4, #{DIRTY}]
    orrs   r0, r1
    str.w  r0, [r4, #{DIRTY}]
    b      v_done
v_give_up:
    movs   r0, #0
    strb.w r0, [r4, #{FAILS}]
v_done:
    add    sp, #28
    pop    {{r4, r5, r6, r7, pc}}
"""
SOURCE['BOOT'] = """
boot:                                 @ start-up, before the main loop
    push   {{r4, r5, r6, r7, lr}}
    sub    sp, #12
    bl     {LAST_INIT}                @ the replaced call
    movw   r4, #{ST_LO}
    movt   r4, #{ST_HI}
    mov    r7, sp
    movs   r5, #0
b_slot:
    lsls   r0, r5, #6                 @ read the slot's record
    adds   r0, #{RECORD}
    mov    r1, r7
    movs   r2, #{RECORD_LEN}
    bl     {EEPROM_READ}
    add.w  r6, r4, #{CACHE}
    add.w  r6, r6, r5, lsl #3
    ldrb   r2, [r7]                   @ the tag, lengths of 16 or less, the check
    cmp    r2, #{TAG}
    bne    b_clear
    movs   r0, #1
b_check:
    ldrb   r3, [r7, r0]
    cmp    r3, #16
    bhi    b_clear
    add    r2, r3
    adds   r0, #1
    cmp    r0, #9
    blo    b_check
    mvns   r2, r2
    uxtb   r2, r2
    ldrb   r3, [r7, #9]
    cmp    r2, r3
    bne    b_clear
    movs   r0, #0
b_copy:
    adds   r1, r0, #1
    ldrb   r3, [r7, r1]
    strb   r3, [r6, r0]
    adds   r0, #1
    cmp    r0, #8
    blo    b_copy
    b      b_next
b_clear:
    movs   r0, #0
    str    r0, [r6]
    str    r0, [r6, #4]
b_next:
    adds   r5, #1
    cmp    r5, #32
    blo    b_slot
    mrs    r6, primask                @ ready: the loaded pattern gets its lengths
    cpsid  i
    movs   r0, #1
    strb.w r0, [r4, #{LOADED}]
    movw   r0, #{SLOT_LO}
    movt   r0, #0x2000
    ldrh   r0, [r0]
    bl     APPLY_ADDRESS
    msr    primask, r6
    add    sp, #12
    pop    {{r4, r5, r6, r7, pc}}
"""
SOURCE['SHOW'] = """
show:                                 @ the light builder, playing: r0 = the step lights, r3 = 1
    push   {{r3, r4, r5, lr}}
    bl     {STEP_LIGHT}               @ the replaced call: r2 = the running light's step (v1.2)
    movw   r1, #{MODE_LO}
    movt   r1, #0x2000
    ldrb   r1, [r1]
    cmp    r1, #3                     @ Pattern Write
    bne    w_done
    movw   r1, #{SCALE_LO}
    movt   r1, #0x2000
    ldr    r1, [r1]
    cbnz   r1, w_done                 @ the lights show the scale instead
    movw   r1, #{ROW_PTR_LO}
    movt   r1, #0x2000
    ldr    r1, [r1]                   @ the selected voice's row in the playing pattern
    movw   r3, #{ROW0_LO}
    movt   r3, #0x2000
    subs   r1, r1, r3
    cmp    r1, #16                    @ rows 0-8, 2 bytes each: accent, BD..CH
    bhi    w_done
    lsrs   r3, r1, #1
    bhs    w_done                     @ carry: an odd offset isn't a row
    movw   r4, #{ST_LO}
    movt   r4, #{ST_HI}
    add    r3, r4
    ldrb.w r3, [r3, #{LEN}]           @ its own length, 0 = it follows the pattern
    cbz    r3, w_done
    ldr    r5, [r4, #{N}]             @ the step it last played: (steps since Start - 1) mod length
    cbz    r5, w_mask
    subs   r5, #1
    udiv   r1, r5, r3
    mls    r2, r1, r3, r5
w_mask:
    movs   r1, #1                     @ steps past its length stay dark
    lsls   r1, r3
    subs   r1, #1
    ands   r0, r1
w_done:
    pop    {{r3, r4, r5, pc}}
"""
SOURCE['LATCH'] = """
latch:                                @ PANEL p_mode: r6 = HELD (a voice's key), r7 = ST, fp = the keys
    ldrb.w r0, [r7, #{LATCHED}]
    cbz    r0, t_held
    ldr    r0, [r7, #{TICK}]          @ latched: it closes after TIMEOUT
    ldr.w  r1, [r7, #{LATCH_T}]
    subs   r0, r0, r1
    movw   r1, #{TIMEOUT}
    cmp    r0, r1
    blo    t_done
    b      t_close
t_held:
    add.w  r0, fp, r6, lsl #3         @ the replaced instruction: the held button's state
    ldrb   r0, [r0]
    cmp    r0, #3
    bhs    t_done                     @ still held
    ldr    r0, [r7, #{TICK}]          @ let go: was its length on show, with none chosen?
    ldr    r1, [r7, #{HELD_T}]
    subs   r0, r0, r1
    movw   r1, #{WINDOW}
    cmp    r0, r1
    blo    t_close
    ldrb.w r0, [r7, #{CHOSEN}]
    cbnz   r0, t_close
    movs   r0, #1                     @ then the view stays, and HELD still names the voice
    strb.w r0, [r7, #{LATCHED}]
    ldr    r0, [r7, #{TICK}]
    str.w  r0, [r7, #{LATCH_T}]
    b      t_done
t_close:
    movs   r6, #0                     @ as v1.3 when the button is let go
    strb.w r6, [r7, #{HELD}]
    strb.w r6, [r7, #{LATCHED}]
t_done:
    b.w    {SCAN_START}
"""
SOURCE['NEWHOLD'] = """
newhold:                              @ PANEL p_plain: a voice's button was pressed, r3 = its key
    strb.w r3, [r7, #{HELD}]          @ the replaced instruction
    movs   r0, #0                     @ a new hold: nothing chosen, not latched
    strb.w r0, [r7, #{LATCHED}]
    strb.w r0, [r7, #{CHOSEN}]
    bx     lr
"""
SOURCE = {name: text.format(**{k: (hex(v) if isinstance(v, int) else v) for k, v in _F.items()})
          for name, text in SOURCE.items()}
ORDER = ('APPLY', 'LOAD', 'SET', 'SAVE', 'BOOT', 'SHOW', 'LATCH', 'NEWHOLD')
START = 0x0800D300
SET_LENGTH_STORE = 0x0800D1C0       # v1.3 PANEL's set_length: strb.w r1, [r0, #LEN]


def listing(name, apply_address):
    return SOURCE[name].replace('APPLY_ADDRESS', hex(apply_address))


# GENERATED
ADDRESS = {'APPLY': 0x800d300, 'LOAD': 0x800d328, 'SET': 0x800d34c, 'SAVE': 0x800d3b0, 'BOOT': 0x800d464, 'SHOW': 0x800d4ec, 'LATCH': 0x800d550, 'NEWHOLD': 0x800d5a4}
BODY = {
    'APPLY': bytes.fromhex('10f03f0f0ed1b0f5006f0bd204ebd00000f1680004f12d010022835c8b540132082afad37047'),
    'LOAD': bytes.fromhex('10b5f8f721fc42f20014c2f2000494f8600030b140f28820c2f200000088fff7dbff10bd'),
    'SET': bytes.fromhex('0cb4eff3108372b680f82c1097f86020dab140f28822c2f20002128812f03f0f13d1b2f5006f10d2c01b00ebd200384480f86710920901209040d7f864200243c7f86420002087f86100012087f8590097f8580010b13868c7f85c0083f310880cbc7047'),
    'SAVE': bytes.fromhex('f0b587b0f6f7d4f942f20014c2f2000494f8600000284bd0d4f86400002520fa05f1c90703d10135202df8d340e00121a9408843c4f8640004f1680101ebc5016f4653223a7000200b5c01303b541a440828f9d3d2437a72a801163039460a22f6f713faa801163007f10c010a22f6f7fdf90020395c3a18127b914206d101300a28f7d3002084f8610011e094f8610003280ad2013084f861000121a940d4f864000843c4f8640002e0002084f8610007b0f0bd'),
    'BOOT': bytes.fromhex('f0b583b0f7f718fd42f20014c2f200046f460025a801163039460a22f6f7ccf904f1680606ebc5063a78532a14d101203b5c102b10d81a4401300928f8d3d243d2b27b7a9a4207d10020411c7b5c335401300828f9d302e00020306070600135202dd7d3eff3108672b6012084f8600040f28820c2f200000088fff70fff86f3108803b0f0bd'),
    'SHOW': bytes.fromhex('38b5fff74ffc40f26021c2f200010978032926d140f23021c2f20001096801bb40f26431c2f20001096840f6a023c2f20003c91a102914d84b0812d242f20014c2f20004234493f82c3053b1e56825b1013db5fbf3f101fb1352012199400139084038bd'),
    'LATCH': bytes.fromhex('97f8580040b13868d7f85c10401a43f2c82188421bd315e00bebc6000078032815d23868f96b401a40f62821884209d397f8590030b9012087f858003868c7f85c0004e0002687f8276087f85860fff77ebd'),
    'NEWHOLD': bytes.fromhex('87f82730002087f8580087f859007047'),
}
# END GENERATED

def sites():
    """(name, address, MIDI-build bytes, new bytes) for every change outside the new code."""
    return [
        ('pattern load', 0x0800366A, bytes.fromhex('02f081fa'), branch(0x0800366A, ADDRESS['LOAD'], link=True)),
        ('main-loop save', 0x080072F6, bytes.fromhex('fcf733fa'), branch(0x080072F6, ADDRESS['SAVE'], link=True)),
        ('start-up', 0x080093A0, bytes.fromhex('fbf77cfd'), branch(0x080093A0, ADDRESS['BOOT'], link=True)),
        ('set length', SET_LENGTH_STORE, bytes.fromhex('80f82c10'), branch(SET_LENGTH_STORE, ADDRESS['SET'], link=True)),
        ('Write lights', LIGHT_SITE, branch(LIGHT_SITE, STEP_LIGHT, link=True), branch(LIGHT_SITE, ADDRESS['SHOW'], link=True)),
        ('length view let go', LATCH_SITE, bytes.fromhex('0bebc600'), branch(LATCH_SITE, ADDRESS['LATCH'])),
        ('new hold', HOLD_SITE, bytes.fromhex('87f82730'), branch(HOLD_SITE, ADDRESS['NEWHOLD'], link=True)),
        ('start-up clear size', 0x0800BC58, (0x100 + V.SIZE + 2).to_bytes(4, 'little'), (0x100 + END).to_bytes(4, 'little')),
    ]
