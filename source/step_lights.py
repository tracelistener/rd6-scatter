"""Step lights follow the step Scatter actually plays (first tried in the v1.1 test
build, confirmed on hardware, now part of Scatter v1.2).

Stock 1.0.5 builds the running step light from the clock step at 0x080064EA
(ldrb.w r2, [r8, #8], r8 = transport 0x20000BB4). The change replaces that one
instruction with BL to the routine below. It returns the step from Scatter's
direction snapshot (0x20002070: clock step bits 0-4, length 5-9, played step
10-14, tag 0xD1000000) when the snapshot is tagged, matches the current clock
step and pattern length (0x20000A9C+2), and lies inside the pattern.
Otherwise it returns the clock step, exactly as stock. Only r1, r2 and the
flags change; r1 is overwritten by the next instruction at the call site.

    0x0800CD90  push    {r0, r3, lr}
                ldrb.w  r2, [r8, #8]        ; stock: clock step
                ldr     r1, =0x20002070     ; direction snapshot
                ldr     r1, [r1]
                lsrs    r0, r1, #15
                cmp.w   r0, #0x1A200        ; tag 0xD1000000 >> 15
                bne     done
                and     r0, r1, #31         ; snapshot clock step
                cmp     r0, r2
                bne     done
                ubfx    r0, r1, #5, #5      ; snapshot length
                ldr     r3, =0x20000A9C     ; playing pattern
                ldrb    r3, [r3, #2]        ; its length
                cmp     r0, r3
                bne     done
                ubfx    r0, r1, #10, #5     ; played step
                cmp     r0, r3
                bhs     done
                mov     r2, r0
    done:       pop     {r0, r3, pc}
                nop                         ; literal pool alignment
"""
SITE = 0x080064EA
SITE_STOCK = bytes.fromhex('98f80820')   # ldrb.w r2, [r8, #8]
SITE_BL = bytes.fromhex('06f051fc')      # bl 0x0800CD90
# Free space right after v1's code. Not at 0x0800CE00: the updater recovers the XOR
# mask from the longest run of identical 128-byte blocks, which must stay >= 100 blocks,
# and v1's run is exactly 100 blocks starting there.
CAVE = 0x0800CD90
BODY = bytes.fromhex('09b598f808200b490968c80bb0f5d13f0ed101f01f0090420ad1c1f34410064b'
                     '9b78984204d1c1f38420984200d2024609bd00bf702000209c0a0020')
SNAPSHOT = 0x20002070   # rd6_source_mask stores it: 0x20002060 + 0x10 (536879216 in the .ll)
TRANSPORT = 0x20000BB4
PATTERN = 0x20000A9C
