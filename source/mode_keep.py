"""Scatter v1.2: Scatter stays on when Pattern Play switches to Pattern Write.

Before v1.2, two checks reset Scatter whenever the mode byte (0x20000260) was not
2 (Pattern Play). The panel tick cancelled the layer, and the direction check
cleared the direction back to Forward. v1.2 treats mode 3 (Pattern Write) as
"keep everything, but handle no Scatter buttons":

Panel tick (0x0800BEFC, after panel cleanup; r5 = playing, r6 = busy, r7 = mode).
At 0x0800BF14, `eor r0, r7, #2` becomes `b.w 0x0800CDCC`:
    0x0800CDCC  cbz   r5, cancel        ; stopped: cancel, as before
                cbnz  r6, cancel        ; busy: cancel, as before
                cmp   r7, #3            ; Pattern Write: keep the layer, and leave
                beq   keep              ;   every button to the RD-6
                cmp   r7, #2            ; any other mode: cancel, as before
                bne   cancel
                b.w   0x0800BF2A        ; Pattern Play: original START/STOP check
    cancel:     b.w   0x0800BF32        ; original cancel path
    keep:       b.w   0x0800BF3E        ; original return, without cancelling

Direction check (0x0800CCE8, leaf; r0 = mode, after the stopped test).
At 0x0800CCF6, `cmp r0, #2; it eq` becomes `b.w 0x0800CDE4`:
    0x0800CDE4  cmp   r0, #2
                beq   keep
                cmp   r0, #3
                beq   keep
                b.w   0x0800CCFC        ; original clear path
    keep:       bx    lr                ; direction kept
"""
PANEL_SITE = 0x0800BF14
PANEL_SITE_STOCK = bytes.fromhex('87f00200')   # eor r0, r7, #2
PANEL_SITE_NEW = bytes.fromhex('00f05abf')     # b.w 0x0800CDCC
PANEL_CAVE = 0x0800CDCC
PANEL_BODY = bytes.fromhex('35b12eb9032f05d0022f01d1fff7a7b8fff7a9b8fff7adb8')
PANEL_CONTINUE, PANEL_CANCEL, PANEL_KEEP, PANEL_PROCESS = 0x0800BF2A, 0x0800BF32, 0x0800BF3E, 0x0800BF44

DIRECTION_FUNCTION = 0x0800CCE8
DIRECTION_END = 0x0800CD16      # after its final bx lr; data follows
DIRECTION_SITE = 0x0800CCF6
DIRECTION_SITE_STOCK = bytes.fromhex('022808bf')   # cmp r0, #2; it eq
DIRECTION_SITE_NEW = bytes.fromhex('00f075b8')     # b.w 0x0800CDE4
DIRECTION_CAVE = 0x0800CDE4
DIRECTION_BODY = bytes.fromhex('022803d0032801d0fff786bf7047')
DIRECTION_STATE = 0x20002060    # direction, phase, length, seed, snapshot, initialised, effective
MODE = 0x20000260
