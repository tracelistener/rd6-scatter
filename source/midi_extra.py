"""MIDI extra-hit test build on Scatter v1.3. No new RAM.

Scatter's Roll and Ratchet repeats and the 1/32 roll's second hit in mute and
roll mode also send their notes on MIDI out, as the RD-6 sends its regular hits.

STOCK serializes every caller of the existing queue entry. SAFE holds the
same interrupt mask across its capacity check and stock enqueue. FILTER sends
the hit mask before the analog-only clap filter, then resumes that filter
unchanged. MID sends the notes of the 1/32 roll's second hit when v1.3's TICK
fires it, then finishes TICK. No USB/UART work, waits, or note-off code runs in
TIMER14.

v1.3's extra-hit filter (mute_roll FILTER, called at 0x0800BB0A) branches to
0x0800B560, so FILTER here sees the hits after v1.3 has applied the mutes and
each voice's own length: muted voices send no extra notes. MID sends the pins
TICK raised (GPIOC in MID_C, the cymbal's PB15 in MID_B) with the accent of
the step that armed it (bit 0 of the stand-in pattern's accent row), which is
what the accent pin still holds when the second hit fires.
"""
from mute_roll import branch, parse
import mute_roll as V

START = 0x0800D200
ORDER = ('STOCK', 'SAFE', 'FILTER', 'MID')
# v1.3's TICK, where the armed 1/32 hit fires: `movs r0, #21; str r0, [r5]` loads the
# trigger counter, then t_done (`ldr r0, [r5]; cmp r0, #0`) resumes the stock countdown.
MID_SITE = 0x0800CF9C
MID_RESUME = 0x0800CFA0
SOURCE = {}
SOURCE['STOCK'] = '''
    push {r4, lr}
    mrs r4, primask
    cpsid i
    ldr r2, cur
    ldr r3, buf
    bl 0x08002dd8
    msr primask, r4
    pop {r4, pc}
    .align 2
cur: .word 0x20000308
buf: .word 0x200010a7
'''
SOURCE['SAFE'] = '''
    push {r4, r5, r6, lr}
    mrs r4, primask
    cpsid i
    ldr r5, cur
    ldr r1, [r5, #24]
    adds r1, #1
    cmp r1, #100
    bne next
    movs r1, #0
next:
    ldr r2, [r5, #28]
    subs r2, r2, r1
    bpl on_positive
    adds r2, #100
on_positive:
    cmp r2, #8
    bls done
    ldr r2, [r5, #32]
    subs r2, r2, r1
    bpl off_positive
    adds r2, #100
off_positive:
    cmp r2, #8
    bls done
    bl 0x08002dd4
done:
    msr primask, r4
    pop {r4, r5, r6, pc}
    .align 2
cur: .word 0x20000308
'''
# SAFE's address is resolved by the assembler; data order matches rd6_output_frame.
SOURCE['FILTER'] = '''
    push {r0, r1, r4, r5, r6, lr}
    mov r4, r0
    movs r5, #0
    adr r6, notes
loop:
    ldrb r1, [r6, r5]
    movs r2, #1
    lsls r2, r1
    tst r4, r2
    beq skip
    add r0, r6, #8
    ldrb r0, [r0, r5]
    and r1, r4, #1
    orr r0, r0, r1, lsl #7
    bl SAFE_ADDRESS
skip:
    adds r5, #1
    cmp r5, #8
    blo loop
    pop {r0, r1, r4, r5, r6, lr}
    and r2, r0, #1
    b.w 0x0800b564
    .align 2
notes: .byte 1,2,3,4,5,7,8,6,36,40,45,50,51,46,42,39
'''
# Entered by b.w from TICK with r2 = v1.3's state, r3 = GPIOC BOP and r5 = the trigger
# counter; r1, r3, r4 and r5 are live in the stock countdown, r0 and r6 are not.
# bits: each voice's pin as a bit of MID_C | MID_B >> 12 (PB15 lands on unused bit 3),
# in the stock dispatcher's note order BD SD LT HT CY OH CH. The clap never gets a
# 1/32 hit.
SOURCE['MID'] = f'''
    push {{r1, r2, r3, r4, r5, r6, r7, lr}}
    ldr r4, [r2, #{V.MID_C}]
    ldr r0, [r2, #{V.MID_B}]
    orr r4, r4, r0, lsr #12
    ldrh r7, [r2, #{V.FAKE + 4}]
    and r7, r7, #1
    lsls r7, r7, #7
    movs r5, #0
    adr r6, bits
loop:
    ldrb r1, [r6, r5]
    lsr r1, r4, r1
    lsls r1, r1, #31
    beq skip
    adds r0, r6, #7
    ldrb r0, [r0, r5]
    orrs r0, r7
    bl SAFE_ADDRESS
skip:
    adds r5, #1
    cmp r5, #7
    blo loop
    pop {{r1, r2, r3, r4, r5, r6, r7, lr}}
    movs r0, #21
    str r0, [r5]
    b.w {MID_RESUME:#x}
    .align 2
bits: .byte 13,14,15,0,3,1,2,36,40,45,50,51,46,42
'''


def listing(name, safe):
    """SOURCE[name] with SAFE's address filled in."""
    return SOURCE[name].replace('SAFE_ADDRESS', hex(safe))


# GENERATED
ADDRESS = {'STOCK': 134271488, 'SAFE': 134271520, 'FILTER': 134271580, 'MID': 134271652}
BODY = {
    'STOCK': bytes.fromhex('10b5eff3108472b6034a044bf5f7e4fd84f3108810bd00bf08030020a7100020'),
    'SAFE': bytes.fromhex('70b5eff3108472b60b4da9690131642900d10021ea69521a00d56432082a07d92a6a521a00d56432082a01d9f5f7c2fd84f3108870bd00bf08030020'),
    'FILTER': bytes.fromhex('73b5044600250ca6715d01228a40144208d006f10800405d04f0010140eac110fff7d0ff0135082deed3bde8734000f00102fef769b900bf010203040507080624282d32332e2a27'),
    'MID': bytes.fromhex('feb51469506944ea1034b2f8447007f00107ff0100250aa6715d24fa01f1c90704d0f01d405d3843fff7a8ff0135072df2d3bde8fe4015202860fff75fbe00bf0d0e0f0003010224282d32332e2a'),
}
# END GENERATED

def sites():
    return [(0x08002DD4, bytes.fromhex('064a054b'), branch(0x08002DD4, ADDRESS['STOCK'])),
            # Drain offs only through notes whose ons have been consumed. An IRQ
            # may append between the off routine's loads, before the on drain.
            (0x08005534, bytes.fromhex('a169206a'), bytes.fromhex('e169206a')),
            (0x0800B560, bytes.fromhex('00f00102'), branch(0x0800B560, ADDRESS['FILTER'])),
            (MID_SITE, bytes.fromhex('15202860'), branch(MID_SITE, ADDRESS['MID']))]
