"""Scatter v1.3: mute and roll mode, and a loop length for each voice.

Scatter v1.2 plus a performance mode modelled on the Quicksilver 606's MUTE AND ROLL
MODE, and a loop length per voice. In Pattern Play, while a pattern plays,
double-click FUNCTION to enter or leave mute and roll mode:

    steps 1-8          mute or unmute BD, SD, LT, HT, CY, CP, OH, CH
    steps 9-16         roll on or off for the same voices
    PATTERN GROUP      mute or unmute the accent
    TAP + steps 9-14   roll rate: off, 1/32, 1/16, 1/8, 1/4, 1/2 (starts off)
    TAP + 15 / 16      all rolls off / unmute everything
    hold 1-8, then a step   that voice loops over that many steps
    hold 1-8, then TAP      that voice follows the pattern length again

A press of 1-8 mutes or unmutes at once, and several can be pressed together. Holding
one for WINDOW ticks (about 0.4 s) cancels that press's mute change and lights the
voice's length (steps 1 to its length); while it is held, a step sets the length.

In the mode the step lights show its state: 1-8 lit = voice playing, 9-16 lit = roll
on. Holding TAP lights the rate (9 = off ... 14 = 1/2). Stopping or leaving Pattern Play ends the mode. Mutes, rolls, the rate and the
lengths stay until the RD-6 is switched off and apply in every mode.

A double-click is two FUNCTION presses, each without any other button, the second
starting less than WINDOW TIMER14 ticks (about 0.4 s) after the first is released. It
takes effect when the second press is released, so FUNCTION + TAP and Scatter's
FUNCTION shortcuts are never mistaken for it.

How it works (stock 1.0.5 and Scatter v1.2 addresses):
- Steps. Scatter's step hook (0x0800BB90) used to resume the stock dispatcher at
  0x08006B32 with r3 = the playing pattern (0x20000A9C: 4 header bytes, then nine
  16-bit rows: accent, BD, SD, LT, HT, CY, CP, OH, CH) and r4 = the step mask Scatter
  chose (1 << step, or 0 when it silences the step). DISPATCH now works out the hits:
  a row that follows the pattern tests r4, as before; a row with its own length L
  plays bit (n mod L), where n counts steps since Start, and is silent when Scatter
  silences the step. Rolls add their rows when n is a multiple of the rate's step
  count, and mutes clear rows last. DISPATCH stores the hits as a one-step stand-in
  pattern (FAKE, bit 0 of each row) and resumes the stock dispatcher with r3 = FAKE
  and r4 = 1, so triggers, accent, the clap's pre-pulse and MIDI notes all go through
  the stock code.
- 1/32 rolls. DISPATCH also arms a second hit at half the measured step (steps of 40
  to 32767 ticks). TICK, at 0x08006E0C in the stock trigger countdown (every TIMER14
  tick), raises those trigger pins when it runs out and loads the trigger counter so
  the extra hit gets a step's 16-tick trigger. The clap is left out (its trigger runs for 340 ticks) and the
  extra hit isn't sent over MIDI.
- Scatter's Roll and Ratchet repeats. FILTER, called in place of rd6_analog_only_hits
  (0x0800B560) at 0x0800BB0A, takes rows with their own length from this step's hits
  and drops muted rows.
- Step lights. LED, at 0x080064FE in the light builder, shows DISPLAY in the mode.
- Buttons. PANEL, at v1.2's Pattern Play exit (0x0800CDD8, b.w 0x0800BF2A), runs only
  in Pattern Play while playing and not busy. Outside the mode it only watches
  FUNCTION and carries on as v1.2. In the mode it handles the steps, TAP and PATTERN
  GROUP, marks them handled with Scatter's rd6_panel_consume (0x0800BE36) so the
  RD-6 doesn't also select patterns or tap the tempo, and returns without Scatter's
  own button handling (0x0800BF3E).
- RAM. The state at ST is cleared at power-on: v1.2's start-up clear of 0x20002000
  (size word at 0x0800BC58) grows from 0x7C to 0x158 bytes.

The code sits from 0x0800CE00 in the blank block run that the updater uses to recover
the update file's mask, which keeps 92 of its 100 blocks; the updater accepts 64.
SOURCE below is assembled by source/assemble_mute_roll.py (keystone, which mis-encodes
some branches silently, so every branch and adr is checked against the listing with
capstone and absolute branches are encoded by branch() here). The generated section
holds its output.
"""
import re

ST = 0x20002100
# RAM state, byte offsets from ST
TICK = 0x00         # u32  TIMER14 ticks
FPRESS_T = 0x04     # u32  tick of the latest FUNCTION press
LAST = 0x08         # u32  tick of the previous step
N = 0x0C            # u32  steps since Start
MID_C = 0x10        # u32  GPIOC pins of the pending 1/32 hit
MID_B = 0x14        # u32  GPIOB pins of the pending 1/32 hit
MUTES = 0x18        # u16  muted rows: bit 0 accent, bits 1-8 BD..CH
ROLLS = 0x1A        # u16  rolled rows, bits 1-8
HPRE = 0x1C         # u16  this step's hits before mutes
LENMASK = 0x1E      # u16  rows with their own length
DISPLAY = 0x20      # u16  step lights in the mode
MID = 0x22          # u16  ticks until the pending 1/32 hit, 0 = none
MUTEMODE = 0x24     # u8
RESTART = 0x25      # u8   set while stopped: the next step is step 0
RATE = 0x26         # u8   0 off, 1 1/32, 2 1/16, 3 1/8, 4 1/4, 5 1/2
HELD = 0x27         # u8   key index of the mute button being held, 0 = none
TOGGLED = 0x28      # u8   the held button toggled its mute when pressed
FPREV = 0x29        # u8   FUNCTION was held on the previous panel tick
FCLEAN = 0x2A       # u8   no other button pressed during this FUNCTION press
ARMED = 0x2B        # u8   a clean FUNCTION click is waiting for the second one
LEN = 0x2C          # u8[9] length per row, 0 = follow the pattern
ARMED_T = 0x38      # u32  tick when the waiting click was released
HELD_T = 0x3C       # u32  tick when the held mute button was pressed
FAKE = 0x40         # stand-in pattern: rows at +4..+21, bit 0 = hit
SIZE = 0x56
WINDOW = 2600       # TIMER14 ticks, about 0.4 s
ROLL_STEPS = (0, 1, 1, 2, 4, 8)          # steps between roll hits per rate
ROLL_PINS_C = (0, 0x2000, 0x4000, 0x8000, 0x0001, 0, 0, 0x0002, 0x0004)   # per row
NO_CLAP = 0x1BE                          # rows 1-5, 7, 8

# Key indexes (0x20000914 + 8 * index, byte 0 = state: 3 = new press, 7 = handled)
KEY_FUNCTION, KEY_STEP1, KEY_GROUP, KEY_TAP = 2, 3, 19, 20

# Stock 1.0.5 / Scatter v1.2 addresses
DISPATCH_RESUME = 0x08006B32    # stock dispatcher after Scatter's step hook
COUNTDOWN_RESUME = 0x08006E10   # stock countdown after `ldr r0, [r5]; cmp r0, #0`
LIGHT_LOOP = 0x08006502         # light builder: LED word from r0
ANALOG_ONLY_HITS = 0x0800B560   # Scatter's rd6_analog_only_hits
PANEL_CONTINUE = 0x0800BF2A     # v1.2 Pattern Play button handling
PANEL_KEEP = 0x0800BF3E         # v1.2 return from rd6_panel_tick
PANEL_CONSUME = 0x0800BE36      # Scatter's rd6_panel_consume(keys, state, aux, key)
PATTERN = 0x20000A9C
TRANSPORT = 0x20000BB4
MODE_BYTE = 0x20000260
SHORT_FLAG = 0x2000035C

_F = dict(ST_LO=ST & 0xFFFF, ST_HI=ST >> 16, **{k: v for k, v in globals().items()
          if k.isupper() and isinstance(v, int)})

SOURCE = {}
SOURCE['DISPATCH'] = """
dispatch:
    push   {{r5, r6, r7}}
    movw   r7, #{ST_LO}
    movt   r7, #{ST_HI}
    ldrb.w r0, [r7, #{RESTART}]
    cbz    r0, d_count
    movs   r0, #0                     @ first step after a stop: n = 0
    strb.w r0, [r7, #{RESTART}]
    str    r0, [r7, #{N}]
    ldr    r0, [r7, #{TICK}]
    str    r0, [r7, #{LAST}]
d_count:
    ldr    r6, [r7, #{N}]             @ r6 = n
    adds   r0, r6, #1
    str    r0, [r7, #{N}]
    ldr    r0, [r7, #{TICK}]
    ldr    r1, [r7, #{LAST}]
    str    r0, [r7, #{LAST}]
    sub.w  sl, r0, r1                 @ sl = ticks since the previous step
    movs   r5, #0                     @ r5 = hits, one bit per row
    mov.w  fp, #0                     @ fp = rows with their own length
    movs   r2, #0                     @ r2 = row: 0 accent, 1 BD ... 8 CH
d_lane:
    add.w  r0, r3, r2, lsl #1
    ldrh   r0, [r0, #4]
    add.w  r1, r7, r2
    ldrb.w r1, [r1, #{LEN}]
    cbz    r1, d_follow
    udiv   r8, r6, r1                 @ own length L: bit n mod L
    mls    r8, r8, r1, r6
    lsr.w  r0, r0, r8
    movs   r1, #1
    lsls   r1, r2
    orr.w  fp, fp, r1
    cmp    r4, #0                     @ silent when Scatter silences the step
    beq    d_next
    lsls   r0, r0, #31
    beq    d_next
    orrs   r5, r1
    b      d_next
d_follow:
    tst    r0, r4                     @ follows the pattern and Scatter's direction
    beq    d_next
    movs   r1, #1
    lsls   r1, r2
    orrs   r5, r1
d_next:
    adds   r2, #1
    cmp    r2, #9
    blo    d_lane
    ldrb.w r0, [r7, #{RATE}]          @ rolls: every R steps from Start
    cbz    r0, d_mute
    adr    r1, roll_steps
    ldrb   r1, [r1, r0]
    udiv   r8, r6, r1
    mls    r8, r8, r1, r6
    cmp.w  r8, #0
    bne    d_mute
    ldrh   r1, [r7, #{ROLLS}]
    orrs   r5, r1
d_mute:
    strh   r5, [r7, #{HPRE}]
    strh.w fp, [r7, #{LENMASK}]
    ldrh   r1, [r7, #{MUTES}]
    bics   r5, r1                     @ mutes last
    movs   r1, #0
    strh   r1, [r7, #{MID}]           @ a new step cancels a pending 1/32 hit
    ldrb.w r0, [r7, #{RATE}]
    cmp    r0, #1
    bne    d_fake
    ldrh   r0, [r7, #{ROLLS}]         @ 1/32: a second hit halfway through the step
    ldrh   r1, [r7, #{MUTES}]
    bics   r0, r1
    movw   r1, #{NO_CLAP}
    ands   r0, r1
    cbz    r0, d_fake
    push   {{r2, r3}}
    movs   r1, #0
    adr    r2, pin_c
    movs   r3, #1
d_pin:
    lsr.w  r8, r0, r3
    tst.w  r8, #1
    beq    d_pin_next
    ldrh.w r8, [r2, r3, lsl #1]
    orr.w  r1, r1, r8
d_pin_next:
    adds   r3, #1
    cmp    r3, #9
    blo    d_pin
    pop    {{r2, r3}}
    str    r1, [r7, #{MID_C}]
    and    r0, r0, #0x20              @ cymbal: PB15
    lsls   r0, r0, #10
    str    r0, [r7, #{MID_B}]
    lsr.w  r0, sl, #1
    cmp    r0, #20
    blo    d_fake
    cmp.w  r0, #0x4000
    bhs    d_fake
    strh   r0, [r7, #{MID}]
d_fake:
    add.w  r3, r7, #{FAKE}            @ stand-in pattern: bit 0 of each row
    movs   r2, #0
d_fake_lane:
    lsr.w  r0, r5, r2
    and    r0, r0, #1
    add.w  r1, r3, r2, lsl #1
    strh   r0, [r1, #4]
    adds   r2, #1
    cmp    r2, #9
    blo    d_fake_lane
    movs   r4, #1
    pop    {{r5, r6, r7}}
    ldrh   r1, [r3, #4]               @ as Scatter's hook: r1 = accent row, r8 = GPIOC BOP
    movw   r8, #0x0818
    movt   r8, #0x4800
    b.w    {DISPATCH_RESUME}
    .align 2
pin_c:
    .short 0, 0x2000, 0x4000, 0x8000, 0x0001, 0, 0, 0x0002, 0x0004
    .align 2
roll_steps:
    .byte 0, 1, 1, 2, 4, 8
"""
SOURCE['TICK'] = """
tick:
    movw   r2, #{ST_LO}
    movt   r2, #{ST_HI}
    ldr    r6, [r2, #{TICK}]
    adds   r6, #1
    str    r6, [r2, #{TICK}]
    movw   r0, #{TRANSPORT_LO}            @ transport: playing?
    movt   r0, #0x2000
    ldr    r0, [r0]
    cbnz   r0, t_playing
    movs   r6, #1                     @ stopped: next step is step 0, the mode ends
    strb.w r6, [r2, #{RESTART}]
    movs   r6, #0
    strb.w r6, [r2, #{MUTEMODE}]
    strh   r6, [r2, #{MID}]
    b      t_done
t_playing:
    movw   r0, #{MODE_LO}                 @ mode byte: 2 = Pattern Play
    movt   r0, #0x2000
    ldrb   r0, [r0]
    cmp    r0, #2
    beq    t_mid
    movs   r6, #0
    strb.w r6, [r2, #{MUTEMODE}]
t_mid:
    ldrh   r6, [r2, #{MID}]           @ pending 1/32 hit
    cbz    r6, t_done
    subs   r6, #1
    strh   r6, [r2, #{MID}]
    cbnz   r6, t_done
    ldr    r6, [r2, #{MID_C}]
    str    r6, [r3]                   @ GPIOC BOP
    ldr    r6, [r2, #{MID_B}]
    movw   r0, #0x0418
    movt   r0, #0x4800
    str    r6, [r0]                   @ GPIOB BOP
    movw   r0, #{SHORT_FLAG_LO}           @ as a regular hit: short-voice flag and counter, which
    movt   r0, #0x2000                @ counts down from this tick on: 21 gives a step's
    movs   r6, #1                     @ 16-tick trigger
    str    r6, [r0]
    movs   r0, #21
    str    r0, [r5]
t_done:
    ldr    r0, [r5]                   @ the two replaced stock instructions
    cmp    r0, #0
    b.w    {COUNTDOWN_RESUME}
"""
SOURCE['LED'] = """
led:
    movw   r1, #{ST_LO}
    movt   r1, #{ST_HI}
    ldrb.w r4, [r1, #{MUTEMODE}]
    cbz    r4, l_done
    ldrh   r0, [r1, #{DISPLAY}]       @ in the mode, show its state
l_done:
    movs   r1, #0                     @ the two replaced stock instructions
    mov    r4, r3
    b.w    {LIGHT_LOOP}
"""
SOURCE['FILTER'] = """
filter:
    movw   r2, #{ST_LO}
    movt   r2, #{ST_HI}
    ldrh   r3, [r2, #{LENMASK}]       @ rows with their own length: this step's hits
    bics   r0, r3
    ldrh.w ip, [r2, #{HPRE}]
    and.w  ip, ip, r3
    orr.w  r0, r0, ip
    ldrh   r3, [r2, #{MUTES}]         @ drop muted rows
    bics   r0, r3
    b.w    {ANALOG_ONLY_HITS}
"""
SOURCE['PANEL'] = """
panel:
    push   {{r5, r6, r7, r8}}
    movw   r7, #{ST_LO}
    movt   r7, #{ST_HI}
    ldrb.w r0, [fp, #16]              @ FUNCTION's key state, 3 or more = held
    cmp    r0, #3
    ite    hs
    movhs  r0, #1
    movlo  r0, #0
    ldrb.w r1, [r7, #{FPREV}]
    strb.w r0, [r7, #{FPREV}]
    cbz    r0, f_up
    cbnz   r1, f_held
    movs   r2, #1                     @ FUNCTION pressed
    strb.w r2, [r7, #{FCLEAN}]
    ldr    r2, [r7, #{TICK}]
    str    r2, [r7, #{FPRESS_T}]
    ldrb.w r0, [r7, #{MUTEMODE}]
    cbz    r0, f_held
    movs   r3, #2                     @ in the mode FUNCTION is ours
    bl     consume
f_held:
    movs   r3, #0                     @ another button pressed with FUNCTION: not a click
f_scan:
    cmp    r3, #2
    beq    f_next
    add.w  r0, fp, r3, lsl #3
    ldrb   r0, [r0]
    cmp    r0, #3
    bne    f_next
    movs   r0, #0
    strb.w r0, [r7, #{FCLEAN}]
f_next:
    adds   r3, #1
    cmp    r3, #21
    blo    f_scan
    b      p_after_func
f_up:
    cbz    r1, p_after_func
    ldrb.w r0, [r7, #{FCLEAN}]        @ FUNCTION released
    cbz    r0, f_disarm
    ldrb.w r0, [r7, #{ARMED}]
    cbz    r0, f_arm
    ldr    r0, [r7, #{FPRESS_T}]
    ldr    r1, [r7, #{ARMED_T}]
    subs   r0, r0, r1
    movw   r1, #{WINDOW}
    cmp    r0, r1
    bhs    f_arm
    ldrb.w r0, [r7, #{MUTEMODE}]      @ double-click: enter or leave the mode
    eor    r0, r0, #1
    strb.w r0, [r7, #{MUTEMODE}]
    movs   r0, #0
    strb.w r0, [r7, #{HELD}]
    strb.w r0, [r7, #{ARMED}]
    b      p_after_func
f_arm:
    movs   r0, #1                     @ a clean click: wait for a second one
    strb.w r0, [r7, #{ARMED}]
    ldr    r0, [r7, #{TICK}]
    str    r0, [r7, #{ARMED_T}]
    b      p_after_func
f_disarm:
    movs   r0, #0
    strb.w r0, [r7, #{ARMED}]
p_after_func:
    ldrb.w r0, [r7, #{MUTEMODE}]
    cmp    r0, #0
    beq.w  p_continue
p_mode:
    ldrb.w r6, [r7, #{HELD}]
    cbz    r6, p_scan_start
    add.w  r0, fp, r6, lsl #3
    ldrb   r0, [r0]
    cmp    r0, #3
    bhs    p_scan_start
    movs   r6, #0                     @ the held mute button was let go
    strb.w r6, [r7, #{HELD}]
p_scan_start:
    ldrb.w r5, [fp, #160]             @ r5 = TAP's key state
    movs   r3, #3
p_scan:                               @ first new press of steps 1-16 or PATTERN GROUP
    add.w  r0, fp, r3, lsl #3
    ldrb   r0, [r0]
    cmp    r0, #3
    beq    p_hit
    adds   r3, #1
    cmp    r3, #20
    blo    p_scan
    cmp    r5, #3                     @ no step: a new TAP press?
    bne    p_display
    cbz    r6, p_tap_only
    movs   r1, #0                     @ held mute button + TAP: follow the pattern again
    bl     set_length
p_tap_only:
    movs   r3, #20
    bl     consume
    b      p_display
p_hit:
    cmp    r3, #19                    @ PATTERN GROUP: accent mute
    beq    p_group
    cbz    r6, p_nohold
    ldr    r0, [r7, #{TICK}]          @ a mute button held long enough to show its length?
    ldr    r1, [r7, #{HELD_T}]
    subs   r0, r0, r1
    movw   r1, #{WINDOW}
    cmp    r0, r1
    blo    p_nohold
    sub.w  r1, r3, #2                 @ yes: this step sets its length
    bl     set_length
    b      p_consume
p_nohold:
    cmp    r5, #3                     @ TAP held?
    blo    p_plain
    cmp    r3, #17                    @ TAP + 15: all rolls off
    beq    p_rolls_off
    cmp    r3, #18                    @ TAP + 16: unmute everything
    beq    p_unmute_all
    cmp    r3, #11                    @ TAP + 9-14: roll rate
    blo    p_consume
    sub.w  r0, r3, #11
    strb.w r0, [r7, #{RATE}]
    b      p_consume
p_rolls_off:
    movs   r0, #0
    strh   r0, [r7, #{ROLLS}]
    b      p_consume
p_unmute_all:
    movs   r0, #0
    strh   r0, [r7, #{MUTES}]
    b      p_consume
p_plain:
    cmp    r3, #11
    bhs    p_roll
    sub.w  r0, r3, #2                 @ steps 1-8: mute or unmute
    movs   r1, #1
    lsls   r1, r0
    ldrh   r0, [r7, #{MUTES}]
    eors   r0, r1
    strh   r0, [r7, #{MUTES}]
    strb.w r3, [r7, #{HELD}]
    movs   r0, #1
    strb.w r0, [r7, #{TOGGLED}]
    ldr    r0, [r7, #{TICK}]
    str    r0, [r7, #{HELD_T}]
    b      p_consume
p_roll:
    sub.w  r0, r3, #10                @ steps 9-16: roll on or off
    movs   r1, #1
    lsls   r1, r0
    ldrh   r0, [r7, #{ROLLS}]
    eors   r0, r1
    strh   r0, [r7, #{ROLLS}]
    b      p_consume
p_group:
    ldrh   r0, [r7, #{MUTES}]
    eor    r0, r0, #1
    strh   r0, [r7, #{MUTES}]
p_consume:
    bl     consume
p_display:
    ldrb.w r5, [fp, #160]
    cmp    r5, #3
    blo    p_not_tap
    ldrb.w r0, [r7, #{RATE}]          @ TAP held: light the rate, 9 = off ... 14 = 1/2
    adds   r0, #8
    movs   r1, #1
    lsls   r1, r0
    b      p_store
p_not_tap:
    ldrb.w r6, [r7, #{HELD}]
    cbz    r6, p_states
    ldr    r0, [r7, #{TICK}]
    ldr    r1, [r7, #{HELD_T}]
    subs   r0, r0, r1
    movw   r1, #{WINDOW}
    cmp    r0, r1
    blo    p_states                   @ a short press: show the mutes
    bl     undo_toggle                @ held: no mute change; light its length
    sub.w  r0, r6, #2
    add    r0, r7
    ldrb.w r0, [r0, #{LEN}]
    cbnz   r0, p_len
    movw   r0, #{PATTERN_LO}              @ follows the pattern: the pattern's length
    movt   r0, #0x2000
    ldrb   r0, [r0, #2]
p_len:
    movs   r1, #1
    lsls   r1, r0
    subs   r1, #1
    b      p_store
p_states:
    ldrh   r0, [r7, #{MUTES}]         @ 1-8: voices playing, 9-16: rolls on
    mvns   r0, r0
    lsrs   r0, r0, #1
    uxtb   r0, r0
    ldrh   r1, [r7, #{ROLLS}]
    lsrs   r1, r1, #1
    uxtb   r1, r1
    orr.w  r1, r0, r1, lsl #8
p_store:
    strh   r1, [r7, #{DISPLAY}]
p_keep:
    pop    {{r5, r6, r7, r8}}
    b.w    {PANEL_KEEP}
p_continue:
    pop    {{r5, r6, r7, r8}}
    b.w    {PANEL_CONTINUE}
set_length:                           @ r6 = held key, r1 = length, 0 = follow the pattern
    push   {{lr}}
    sub.w  r0, r6, #2
    add    r0, r7
    strb.w r1, [r0, #{LEN}]
    bl     undo_toggle
    ldr    r0, [r7, #{TICK}]          @ show the length straight away
    movw   r1, #{WINDOW}
    subs   r0, r0, r1
    str    r0, [r7, #{HELD_T}]
    pop    {{pc}}
undo_toggle:
    ldrb.w r0, [r7, #{TOGGLED}]
    cbz    r0, u_done
    movs   r0, #0
    strb.w r0, [r7, #{TOGGLED}]
    sub.w  r0, r6, #2
    movs   r1, #1
    lsls   r1, r0
    ldrh   r0, [r7, #{MUTES}]
    eors   r0, r1
    strh   r0, [r7, #{MUTES}]
u_done:
    bx     lr
consume:
    push   {{r3, lr}}
    mov    r0, fp
    mov    r1, r4
    mov    r2, sl
    bl     {PANEL_CONSUME}
    pop    {{r3, pc}}
"""
_F.update(TRANSPORT_LO=TRANSPORT & 0xFFFF, MODE_LO=MODE_BYTE & 0xFFFF,
          SHORT_FLAG_LO=SHORT_FLAG & 0xFFFF, PATTERN_LO=PATTERN & 0xFFFF)
SOURCE = {name: text.format(**{k: (hex(v) if isinstance(v, int) else v) for k, v in _F.items()})
          for name, text in SOURCE.items()}
ORDER = ('DISPATCH', 'TICK', 'LED', 'FILTER', 'PANEL')
START = 0x0800CE00

# --- generated by source/assemble_mute_roll.py: do not edit by hand ---
ADDRESS = {'DISPATCH': 0x0800ce00, 'TICK': 0x0800cf38, 'LED': 0x0800cfa8, 'FILTER': 0x0800cfc0, 'PANEL': 0x0800cfe0}
BODY = {
    'DISPATCH': bytes.fromhex(
        'e0b442f20017c2f2000797f8250028b1002087f82500f8603868b860fe68701cf8603868b968b860a0eb010a00254ff0'
        '000b002203eb4200808807eb020191f82c1079b1b6fbf1f808fb116820fa08f0012191404bea010b002c08d0c00706d0'
        '0d4304e0204202d0012191400d430132092adfd397f8260050b12da1095cb6fbf1f808fb1168b8f1000f01d1798b0d43'
        'bd83a7f81eb0398b8d430021798497f82600012824d1788b398b884340f2be110840e8b10cb4002118a2012320fa03f8'
        '18f0010f03d032f8138041ea08010133092bf3d30cbc396100f02000800278614fea5a00142803d3b0f5804f00d27884'
        '07f14003002225fa02f000f0010003eb420188800132092af5d30124e0bc998840f61808c4f60008f9f70bbe00000020'
        '004000800100000000000200040000bf000101020408'),
    'TICK': bytes.fromhex(
        '42f20012c2f2000216680136166040f6b430c2f20000006838b9012682f82560002682f8246056841ee040f26020c2f2'
        '00000078022802d0002682f82460568c96b1013e56847eb916691e60566940f21840c4f60000066040f25c30c2f20000'
        '012606601520286028680028f9f734bf'),
    'LED': bytes.fromhex(
        '42f20011c2f2000191f8244004b1088c00211c46f9f7a1ba'),
    'FILTER': bytes.fromhex(
        '42f20012c2f20002d38b9843b2f81cc00cea030c40ea0c00138b9843fef7c0ba'),
    'PANEL': bytes.fromhex(
        '2de9e00142f20017c2f200079bf8100003282cbf0120002097f8291087f82900d0b151b9012287f82a203a687a6097f8'
        '240010b1022300f0ebf80023022b07d00bebc3000078032802d1002087f82a000133152bf2d322e009b397f82a00d8b1'
        '97f82b0090b17868b96b401a40f6282188420bd297f8240080f0010087f82400002087f8270087f82b0008e0012087f8'
        '2b003868b86302e0002087f82b0097f82400002800f0948097f827603eb10bebc6000078032802d2002687f827609bf8'
        'a05003230bebc300007803280cd00133142bf7d3032d48d116b1002100f07cf8142300f095f840e0132b38d05eb13868'
        'f96b401a40f62821884204d3a3f1020100f06af82fe0032d10d3112b08d0122b09d00b2b27d3a3f10b0087f8260022e0'
        '002078831fe0002038831ce00b2b0ed2a3f1020001218140388b4840388387f82730012087f828003868f8630be0a3f1'
        '0a0001218140788b4840788303e0388b80f00100388300f053f89bf8a050032d05d397f8260008300121814023e097f8'
        '2760beb13868f96b401a40f62821884210d300f02ff8a6f10200384490f82c0020b940f69c20c2f20000807801218140'
        '013908e0388bc0434008c0b2798b4908c9b240ea01213984bde8e001fef7c7bebde8e001fef7b9be00b5a6f102003844'
        '80f82c1000f006f8386840f62821401af86300bd97f8280048b1002087f82800a6f1020001218140388b484038837047'
        '08b5584621465246fef71dfe08bd'),
}
# --- end of generated section ---


def branch(at, target, link=False):
    """Thumb-2 B.W (T4) or BL (T1) at `at` to `target`."""
    offset = target - (at + 4)
    assert offset % 2 == 0 and -(1 << 24) <= offset < (1 << 24), hex(target)
    s, i1, i2 = (offset >> 24) & 1, (offset >> 23) & 1, (offset >> 22) & 1
    j1, j2 = (1 - i1) ^ s, (1 - i2) ^ s
    hi = 0xF000 | (s << 10) | ((offset >> 12) & 0x3FF)
    lo = (0xD000 if link else 0x9000) | (j1 << 13) | (j2 << 11) | ((offset >> 1) & 0x7FF)
    return hi.to_bytes(2, 'little') + lo.to_bytes(2, 'little')


def sites():
    """(name, address, v1.2 bytes, new bytes) for every change outside the new code."""
    return [
        ('step hook tail', 0x0800BBD4, bytes.fromhex('9988dff8'), branch(0x0800BBD4, ADDRESS['DISPATCH'])),
        ('trigger countdown', 0x08006E0C, bytes.fromhex('28680028'), branch(0x08006E0C, ADDRESS['TICK'])),
        ('light builder', 0x080064FE, bytes.fromhex('00211c46'), branch(0x080064FE, ADDRESS['LED'])),
        ('extra-hit filter', 0x0800BB0A, bytes.fromhex('fff729fd'), branch(0x0800BB0A, ADDRESS['FILTER'], link=True)),
        ('Pattern Play buttons', 0x0800CDD8, bytes.fromhex('fff7a7b8'), branch(0x0800CDD8, ADDRESS['PANEL'])),
        ('start-up clear size', 0x0800BC58, (0x7C).to_bytes(4, 'little'), (0x100 + SIZE + 2).to_bytes(4, 'little')),
    ]


def parse(source):
    """Instructions as [labels, mnemonic, operands], data directives, and label order."""
    instrs, data, pending = [], [], []
    for raw in source.splitlines():
        line = raw.split('@')[0].strip()
        if not line: continue
        m = re.fullmatch(r'(\w+):(.*)', line)
        if m:
            pending.append(m.group(1)); line = m.group(2).strip()
            if not line: continue
        if line.startswith('.'):
            data.append((pending, line)); pending = []
            continue
        assert not data, f'instruction after data: {line}'
        mnemonic, _, operands = line.partition(' ')
        instrs.append((pending, mnemonic, operands.strip())); pending = []
    return instrs, data


BRANCHES = {'b', 'bl', 'cbz', 'cbnz'} | {'b' + c for c in ('eq', 'ne', 'hs', 'lo', 'hi', 'ls', 'ge', 'lt', 'gt', 'le', 'mi', 'pl')}


def check_branches(name, base, code):
    """Every branch and adr in `code` (SOURCE[name] assembled at `base`) lands where the
    listing says, and the data tables match. Returns a list of mismatches."""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
    instrs, data = parse(SOURCE[name])
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    decoded = list(md.disasm(code, base, len(instrs)))
    problems = []
    if len(decoded) != len(instrs):
        return [f'{name}: decoded {len(decoded)} of {len(instrs)} instructions']
    labels = {}
    for (names, mnemonic, _), ins in zip(instrs, decoded):
        for label in names: labels[label] = ins.address
        plain = lambda m: m.split('.')[0]
        if plain(ins.mnemonic) != plain(mnemonic) and not (mnemonic == 'adr' and ins.mnemonic in ('addw', 'adr')):
            problems.append(f'{name} {ins.address:#x}: listing says {mnemonic}, decoded {ins.mnemonic} {ins.op_str}')
    at, table = decoded[-1].address + decoded[-1].size, []
    for names, directive in data:
        kind, _, args = directive.partition(' ')
        if kind == '.align':
            at = (at + (1 << int(args)) - 1) & -(1 << int(args)); continue
        for label in names: labels[label] = at
        size = {'.byte': 1, '.short': 2, '.word': 4}[kind]
        values = [int(v, 0) for v in args.split(',')]
        expected = b''.join(v.to_bytes(size, 'little') for v in values)
        if code[at - base:at - base + len(expected)] != expected:
            problems.append(f'{name}: table at {at:#x} differs from the listing')
        at += len(expected)
    if at - base != len(code):
        problems.append(f'{name}: listing ends at {at:#x}, code at {base + len(code):#x}')
    for (names, mnemonic, operands), ins in zip(instrs, decoded):
        stem = mnemonic.split('.')[0]
        if stem in BRANCHES:
            want = operands.split(',')[-1].strip()
            want = int(want, 0) if want[0].isdigit() else labels[want]
            got = int(ins.op_str.split('#')[-1], 0)
            if got != want: problems.append(f'{name} {ins.address:#x}: {mnemonic} {operands} lands at {got:#x}, not {want:#x}')
        elif stem == 'adr':
            want = labels[operands.split(',')[-1].strip()]
            imm = int(ins.op_str.split('#')[-1], 0)
            got = ((ins.address + 4) & ~3) + (-imm if ins.mnemonic.startswith('sub') else imm)
            if got != want: problems.append(f'{name} {ins.address:#x}: adr gives {got:#x}, not {want:#x}')
    return problems
