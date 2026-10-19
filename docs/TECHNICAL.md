# Technical notes

For people who want to know how Scatter and the updater work, or check them. Players only need the [README](../README.md).

## Repository layout

| Path | Contents |
|---|---|
| `index.html` | Sends the GitHub Pages site to the updater |
| `outputs/rd6_webmidi_uploader.html` | The updater: one self-contained page |
| `outputs/scatter-v1.4.patch.json` | Scatter v1.4 as byte replacements on the official 1.0.5 update file |
| `outputs/check_*.cjs` | Browser checks for the updater (simulated MIDI only) |
| `firmware/` | Behringer's official 1.0.5 and 1.0.6 SysEx update files, unmodified. Source and checksums: `PROVENANCE.json` |
| `scripts/apply_patch.py` | Builds a Scatter `.syx` from the official 1.0.5 file without a browser |
| `source/` | Scatter source (LLVM IR), the 1.0.6-fix backport, the v1.2, v1.3 and v1.4 changes, the v1.3, MIDI step, v1.2, v1 and TEST12 patches that v1.4 is built from, and offline verification scripts |
| `checks/` | Recorded results of offline, simulator and hardware checks |
| `docs/` | User guides and these notes |

## Builds

**Scatter v1.4** is the only build the updater offers. SysEx SHA-256: `f3dd4beca4ebc75d7518b2dac19c3944a32dffde7239438044225b0a61ec9048`. It was built in five steps:

1. **Scatter v1** (`2cdce8d2ae225feb21a153d69669c3406410893e9d1882ac0c8fb5391468b97b`), developed as `TEST14_FIX106`: the hardware-tested `TEST12_GLITCH` (`9bc1c3a74da476c6694724314d275030a7debb4299c561d06cf56f4e55b540ef`) plus a backport of the 1.0.6 pattern-group fix.
2. **Scatter v1.2** (`8bbc359ebdf78357f7233556bf2843d53b34e8a1a52a4f1c0b8b83a9db9d41dc`): v1 plus step lights that follow the played step, and Scatter staying on in Pattern Write ([below](#what-v12-changes)).
3. **Scatter v1.3** (`ff0bb9d18ae7d926f780a65dddda53cb925cb544d3c46a2d5ae1472ff7848fc5`): v1.2 plus mute and roll mode and a loop length per voice ([below](#what-v13-changes)).
4. **MIDI extra hits** (`75f9f392a228ac50779d2dd0107db2d716a6fa95e8ea5d5d9aab7fe9ae70edc2`): v1.3 plus Scatter's Roll and Ratchet repeats and the 1/32 roll's second hit on MIDI out ([below](#midi-extra-hits)). It was offered as a test build first.
5. **Scatter v1.4**: that plus each voice's length saved with its pattern and shown in Pattern Write ([below](#saved-lengths-and-the-pattern-write-display)).

The v1.3, MIDI step, v1.2, v1 and TEST12 patches stay in `source/` only so that each build can be rebuilt from its parent, and so the checks can confirm exactly what each step changes. The updater still recognises a v1.3, MIDI extra-hit test, v1.2, v1 or TEST12 file as an older Scatter build.

Scatter is a patch on official firmware **1.0.5** and reports application version 1.0.5. Behringer's newest firmware is **1.0.6**. Scatter is not a port onto 1.0.6: v1 adds only the documented 1.0.6 fix (keeping a queued pattern number when the pattern group changes during playback) to TEST12, as a 4-byte hook and a 22-byte routine. Its saved Thumb code matched stock 1.0.6 in all 1536 state comparisons of `source/check_fix106.py`, and the effect, panel, timer and startup bytes are unchanged from TEST12 ([checks/TEST14_FIX106.json](../checks/TEST14_FIX106.json)). The diagnostic build marker is still 12 in every Scatter build.

### What v1.2 changes

Built from the v1 patch by `source/build_scatter_v1_2.py` and checked by `source/check_scatter_v1_2.py` ([results](../checks/SCATTER_V1_2.json)). It is Scatter v1 plus two changes, each a short branch to new code below `0x0800CE00`.

**Step lights follow the played step** (`source/step_lights.py`). The stock light builder (`0x0800641C`) draws the running step light from the clock step, read at `0x080064EA` (`ldrb.w r2, [r8, #8]`, where r8 is the transport at `0x20000BB4`). That instruction now calls a 60-byte routine at `0x0800CD90`. The routine reads Scatter's direction snapshot at `0x20002070`, which holds the clock step, the pattern length, the played step and a `0xD1000000` tag. It returns the played step when the snapshot is tagged, matches the current clock step and pattern length, and lies inside the pattern. Otherwise it returns the clock step, exactly as stock. Scatter's step hook writes the snapshot every step and clears it when playback stops or Scatter's direction resets, so outside Scatter the lights behave as before. This change was first tried as a v1.1 test build: the first attempt read `0x20001970` by mistake, and after the fix the lights were confirmed on the test unit.

**Scatter stays on in Pattern Write** (`source/mode_keep.py`). In v1, two checks reset Scatter whenever the mode byte (`0x20000260`) isn't 2 (Pattern Play): the panel tick cancels the layer (`0x0800BF14`), and the direction check clears the direction (`0x0800CCF6`). In v1.2, mode 3 (Pattern Write) while playing keeps the layer and the direction, and the panel handles no Scatter buttons, so the RD-6's own Write controls work. Stopping, a busy panel, START/STOP and every other mode still reset Scatter exactly as in v1.

The check runs the light routine in `source/rd6_thumb_machine.py` from its real call site over 4,794 state combinations. It runs the panel and direction decisions in both v1 and v1.2 for all 84 combinations of mode, playing, busy and START/STOP. It also confirms that v1.2 differs from v1 only at the three call sites and in the three new routines. Both changes were confirmed on the test unit on 2026-10-17.

### What v1.3 changes

SysEx SHA-256 `ff0bb9d18ae7d926f780a65dddda53cb925cb544d3c46a2d5ae1472ff7848fc5`. Scatter v1.2 plus a mute and roll mode modelled on the Quicksilver 606's, and a loop length per voice ([controls](CONTROLS.md#mute-and-roll-mode)). Confirmed on the test unit on 2026-10-17.

The routines are written in Thumb assembly in `source/mute_roll.py`, which also documents every hook and the RAM layout. `source/assemble_mute_roll.py` assembles them with keystone (development only) and stores the bytes in the same file. Keystone can silently encode a branch to an absolute address 2 bytes off, or an out-of-range `cbz`. So absolute branches are re-encoded in Python, and every branch, `adr` and data table is checked against the listing with capstone. `source/build_scatter_v1_3.py` builds the patch from v1.2, and `source/check_scatter_v1_3.py` checks it ([results](../checks/SCATTER_V1_3.json)).

- **Steps.** Scatter's step hook used to resume the stock dispatcher at `0x08006B32` with the playing pattern (`0x20000A9C`) and Scatter's step mask. It now goes through a routine that works out the hits per row:
  - A row that follows the pattern tests the step mask, as before.
  - A row with its own length L plays bit n mod L, where n counts steps since Start. It is silent when Scatter silences the step.
  - Rolls add their rows every 1, 2, 4 or 8 steps, and mutes clear rows last.
  - The hits go to the stock dispatcher as a one-step stand-in pattern, so triggers, accent, the clap's pre-pulse and MIDI notes all use the stock code.
- **1/32 rolls.** The step routine also arms a second hit at half the measured step. A hook at `0x08006E0C` in the stock trigger countdown fires it on the trigger pins with a step's 16-tick trigger. The clap is left out, and the extra hit isn't sent over MIDI.
- **Scatter's Roll and Ratchet repeats.** A filter in place of `rd6_analog_only_hits` (`0x0800BB0A`) substitutes this step's hits for rows with their own length and drops muted rows.
- **Step lights.** A hook at `0x080064FE` in the light builder shows the mode's state.
- **Buttons.** v1.2's Pattern Play exit (`0x0800CDD8`) goes through a routine that watches FUNCTION for a clean double-click, handles the mode's buttons with Scatter's `rd6_panel_consume`, and otherwise carries on as v1.2.
- **RAM.** The state at `0x20002100` is cleared at power-on: v1.2's start-up clear grows from 0x7C to 0x158 bytes.

The 1,020 bytes of new code start at `0x0800CE00`, in the blank block run the updater recovers the mask from, which keeps 92 of its 100 blocks. The updater now needs 64.

The check runs the stock code and the new routines in `source/rd6_thumb_machine.py` on modelled GPIO ports, and compares them with v1.2 with the new state at zero, as at power-on:

- The step dispatcher, entered at the top and run through Scatter's hook, makes the same trigger writes, MIDI notes and RAM changes in 600 random cases, including silenced steps.
- The trigger countdown matches in 1,428 states, the step lights in 200 cases and the Pattern Play buttons in 3,000.

It checks mutes, the accent mute, rolls at every rate, own lengths and restarts against a model over 5,760 steps, on the actual pins and notes. It also measures the 1/32 second hit, checks the extra-hit filter in 400 cases, and checks every button gesture, including the clean double-click rule.

### MIDI extra hits

The first step from v1.3 to v1.4: `source/scatter-v1.3-midi-test.patch.json`, built from the v1.3 patch by `source/build_midi_extra.py` and checked by `source/check_midi_extra.py` ([results](../checks/SCATTER_MIDI_TEST.json)). SysEx SHA-256 `75f9f392a228ac50779d2dd0107db2d716a6fa95e8ea5d5d9aab7fe9ae70edc2`, decoded image `ac0fa39bce04bae0b1279c640df03871d6990c1fb589ca1bbf4d1056dc6f5f9f`. Installed as a test build and played on the test unit on 2026-10-18 ([result](#test-results)). It was first made on v1.2 as a separate test; this version is the same queue protection and repeat notes on v1.3, plus the 1/32 roll's second hit.

**Why v1.3 sends no repeats on MIDI.** Traced in official 1.0.5 and the v1.3 image:

- TIMER13's handler is `0x08007524` and TIMER14's is `0x080075EC`. Their set-up selects AIRCR PRIGROUP `0x500`, then gives IRQ 19 (TIMER13) priority byte `0x50` (`0x080074AA`) and IRQ 20 (TIMER14) `0x00` (`0x0800750E`), so TIMER14 can preempt TIMER13. The check runs these set-up instructions and the stock NVIC helpers rather than assuming priorities.
- The stock dispatcher (`0x08006AE0`) queues note bytes through `0x08002DD4` into a 100-byte ring at `0x200010A7`. Its control block is at `0x20000308`, with the write, note-on and note-off cursors at +`0x18`, +`0x1C` and +`0x20`. The enqueue stores the byte at the write cursor, then publishes the incremented cursor modulo 100, so an enqueue nested in between overwrites the slot and can lose a cursor update. A direct-call trace from the vectors and the main loop finds the enqueue reachable from TIMER2 (`0x08007628`), TIMER13, TIMER14 and the main loop (`0x080093AC`), so protecting one caller isn't enough.
- The main loop calls `0x08005768`, which runs the off drain `0x08005520` and then the on drain `0x08005560`, the only consumers. Each note-on sent uses velocity `0x50`, or `0x70` with accent, and resets one countdown at +`0x24` to 5. The off drain counts it down once per call and at zero sends the pending note-offs with velocity `0x40`. These are main-loop passes, not a fixed time. The send routines `0x0800566C` and `0x08005638` feed USB (`0x08007D24`) and MIDI OUT (`0x08008100`) on the transmit channel.
- Scatter's TIMER14 body (`0x0800BAD8`) runs the scheduler (`0x0800B844`), then v1.3's extra-hit filter (`0x0800CFC0`, which ends in `rd6_analog_only_hits` at `0x0800B560`), then `rd6_stock_fire_hits_analog_only` (`0x0800BABC`). Its MIDI callback (`0x0800BA00`) is a deliberate no-op. Roll silences the regular step through the capture-source-mask hook, so it sends nothing on MIDI, and Ratchet sends only its first hit. v1.3's 1/32 second hit only raises the trigger pins, from TICK in TIMER14's trigger countdown.

**What it changes.** Four routines in `source/midi_extra.py`, 242 bytes at `0x0800D200`–`0x0800D2F1`, and four 4-byte sites. No new RAM.

- **One writer at a time.** `0x08002DD4`, the queue entry every caller uses, branches to STOCK. It saves PRIMASK, masks interrupts, reloads the two displaced literals, runs the original enqueue body at `0x08002DD8` and restores the saved mask. An interrupt arriving before `cpsid i` completes first; one arriving after it waits until the cursor is published. Restoring a saved mask of 1 never enables interrupts. NMI and HardFault don't queue notes.
- **Room check.** SAFE holds the mask across a check of both reader cursors and the enqueue. It drops the extra note when the write would leave 8 or fewer free slots before either reader, which keeps room for a regular step's 8 notes. Nothing waits or retries, so no note can play late after a release or STOP. Regular notes keep the stock unchecked enqueue.
- **Scatter's repeats.** `0x0800B560`, the start of `rd6_analog_only_hits`, branches to FILTER. It queues the notes of the 9-bit hit mask in the dispatcher's order (BD SD LT HT CY OH CH CP) and accent encoding, then runs the displaced instruction and resumes the filter at `0x0800B564`. v1.3's filter runs first, so muted voices send nothing and a voice with its own length sends this step's hit. A clap that the analog filter drops because it would need the accent pre-pulse (accented, or PB2 high) is still sent on MIDI; the scheduler's busy-clap suppression is unchanged.
- **1/32 rolls.** In v1.3's TICK, the instruction pair that loads the trigger counter when the second hit fires (`0x0800CF9C`, `movs r0, #21; str r0, [r5]`) branches to MID. MID queues a note for each pin TICK raised (MID_C, and the cymbal's PB15 in MID_B), in the dispatcher's order and with the accent of the step that armed it: bit 0 of the stand-in pattern's accent row, which is what the accent pin PC6 still holds. It then runs the two instructions and resumes TICK at `0x0800CFA0`, with every register the countdown uses restored.
- **Matching note-offs.** The off drain used to stop at the write cursor. If TIMER14 queued notes during the drain, they could get their note-offs before their note-ons, and then no final note-off. One halfword at `0x08005534` (`ldr r1, [r4, #0x18]` becomes `ldr r1, [r4, #0x1C]`) makes it stop at the note-on cursor, so only notes already sent are released. Without interleaving the output is identical.

The masked sections contain only SRAM accesses and integer arithmetic: no output routine, peripheral access, wait or loop. FILTER and MID unmask between notes. In the interpreter the stock enqueue stays masked for at most 12 instructions and an extra note for at most 36. That isn't a measured latency: Cortex-M timing, peripheral deadlines, stack use and MIDI OUT bandwidth weren't measured, on hardware or offline.

The build differs from v1.3 only at the four sites and in the new code, and v1.3's routines are unchanged apart from TICK's instruction pair. The longest blank run is 90 blocks.

`source/check_midi_extra.py` runs the actual bytes in `source/rd6_thumb_machine.py`, which now models PRIMASK (`mrs`, `msr`, `cpsid i`, decoded in capstone's M-class mode). An interrupt is taken only while PRIMASK is clear, with the register, flag and IT context saved and a 32-byte frame reserved on the stack. It checks:

- The firmware audit above, on stock 1.0.5: priorities, the queue's producers and consumers, the only three cursor stores, and that the trigger countdown runs only in TIMER14.
- 4,265 preemption cases: a stock enqueue interrupted at every instruction boundary and every wrap position, by Scatter's repeats and by a firing 1/32 hit, and the room check interrupted by a stock enqueue. 160 cases of the drains interrupted part-way, where every note still gets its final note-off. 20,000 room-check cases, with either reader lagging.
- All 512 hit masks with both PB2 states at the filter entry (exact note bytes, the analog result, registers and stack), and 400 cases through v1.3's filter with random mutes and lengths.
- TIMER14's body for 600 ticks in every effect mode, including Ratchet with 2 and 4 hits and straight and triplet Roll with Latch off and on, with and without mutes and own lengths, side by side with v1.3. The analog repeats are v1.3's, and MIDI gets the repeats' notes on their ticks with matching note-offs. At a 480-tick step, straight Roll at depth 4 repeats every 240 ticks and triplet every 160. STOP cancels pending repeats without queuing anything.
- The step dispatcher with random v1.3 state (600 cases) and the trigger countdown in 1,428 states match v1.3 exactly: pins, registers and RAM, including the queue. In the 227 of those states where a 1/32 hit fires, the queue then holds exactly its notes.
- A 1/32 roll end to end: the dispatcher arms it, the countdown fires it half a step later on the right pins, its notes reach the wire with the step's accent and their note-offs, and a new step or STOP cancels it.
- With `--mutations`: five deliberately broken builds (MID without the accent or without its notes, no 1/32 hook, STOCK without the mask, the old off-drain bound) each fail at least one check.

While it was a test build, the browser checks covered its option in the updater: unticked by default, the exact pinned install (378 ACKs), the saved `.syx`, the choice kept across Reconnect, and a modified patch refused before anything is sent.

### Saved lengths and the Pattern Write display

The second step, which makes Scatter v1.4: `outputs/scatter-v1.4.patch.json`, built from the MIDI extra-hit patch by `source/build_saved_lengths.py` and checked by `source/check_saved_lengths.py` ([results](../checks/SCATTER_V1_4.json)). SysEx SHA-256 `f3dd4beca4ebc75d7518b2dac19c3944a32dffde7239438044225b0a61ec9048`, decoded image `de68d77e7ee9639730257e37be6fb31dceb3217bed651ef0ba6e3c8cf5d5138d`. Installed as the saved lengths test build and played on the test unit on 2026-10-18 ([result](#test-results)).

**How 1.0.5 keeps patterns.** Traced in the stock firmware and checked by the script:

- The EEPROM is a 32 KB I2C part (device `0xA0`) driven by bit-banged code on GPIOB, with no lock. Everything goes through `eeprom_read(address, buffer, length)` at `0x0800381C` and `eeprom_write` at `0x0800383A`, which waits 5 ms after each write. Nothing else calls the I2C code.
- Pattern *p* of group *g* lives in a 64-byte slot at (16*g* + *p*) × 64. All 35 EEPROM calls in 1.0.5 are listed in the check: every one that touches a slot covers its first 22 bytes (the pattern) or a single byte inside them. Bytes 22–63 of every slot are never read or written. Songs are at `0x1000`, settings at `0x3000` and `0x3080`.
- `0x08003630` loads the playing pattern (`0x20000A9C`) when its slot changes and keeps the slot's address at `0x20000288`. It runs from the main loop, and from TIMER2, TIMER13 and TIMER14 at Start and at the end of a pattern, so the stock firmware already reads EEPROM inside its timers there.
- SysTick (`0x080071C4`) asks for a save about every half second. The main loop then runs `0x080072E4`: the playing pattern's save, then the song's. Each write is read back and any byte that differs is written again, because a timer's pattern load can cut into it.
- The RAM above the stack (`0x20001730`) is free. Scatter uses `0x20002000`–`0x2000207F` and v1.3 `0x20002100`–`0x20002157`.

**What v1.4 changes.** Six routines in `source/saved_lengths.py`, 570 bytes from `0x0800D300`, five 4-byte sites and the start-up clear. Each record is 10 bytes at offset 22 of the pattern's own slot: a tag (`0x53`), the 8 lengths (BD..CH, 0 = follow the pattern, 1–16) and the low byte of the inverted sum of those 9 bytes. Anything else in those bytes means no saved lengths.

- **Start-up.** The last start-up call (`0x080093A0`) goes through BOOT, which reads all 32 records into a RAM copy (CACHE, 8 bytes a slot) and gives the loaded pattern its lengths. Nothing is playing yet, so no timer reads EEPROM meanwhile.
- **Pattern loads.** In `0x08003630`, the call to the pattern tidy-up (`0x0800366A`) goes through LOAD, which then copies the new pattern's lengths from CACHE to v1.3's LEN. It touches only RAM, so it's safe in the timers, and it does nothing until BOOT has filled CACHE.
- **Setting a length.** In v1.3's set_length, the LEN store (`0x0800D1C0`) goes through SET, which also stores the length in CACHE for the playing pattern's slot and marks the slot. It masks interrupts across both stores (23 instructions at most), so a pattern load can't come between them, and keeps every register the panel code uses.
- **Saving.** In `0x080072E4`, the call to the song save (`0x080072F6`) goes through SAVE, which then writes one marked slot's record, reads it back and, if it differs, marks the slot again, at most 3 times in a row. A save that a timer's pattern load cuts into is lost at worst, and retried. One that lands just before a pattern change can make that load wait for the EEPROM, up to the stock driver's 5 ms of retries. The stock pattern saves already carry that risk.
- **Pattern Write's lights.** The light builder (`0x0800641C`, main loop) shows the selected voice's row of the playing pattern (its address is at `0x20000364`), then inverts the running light from v1.2's step routine. While a pattern plays, that call (`0x080064EA`) goes through SHOW. In Pattern Write, when the selected voice has its own length *L*, SHOW moves the running light to the step the voice last played, (steps since Start − 1) mod *L*, and clears its steps past *L*, which don't play. The scale display (`0x20000230`), the other modes and voices that follow the pattern are unchanged.
- **RAM.** LOADED, FAILS, DIRTY and CACHE follow v1.3's state, at `0x20002160`–`0x20002267`. v1.2's start-up clear of `0x20002000` grows from `0x158` to `0x268` bytes.

v1.4 differs from the MIDI step only at the sites and in the new code. The MIDI routines are unchanged, and so are v1.3's apart from set_length's store. The longest blank run is 85 blocks.

`source/check_saved_lengths.py` runs the actual bytes against a model of the EEPROM. The two EEPROM routines become stubs that read or write the model, writes wrap inside a 64-byte page, and the rest of the stock code runs as it is. It checks:

- The stock audit above: the list of EEPROM calls, and six stock pattern paths (load, SysEx read and restore, the playing pattern's save, the tidy-up's save, factory reset) run on the model with every slot's bytes 22–63 left as they were.
- Start-up over 200 random EEPROMs: one read per slot and no writes, valid records cached, and wrong tags, lengths over 16, wrong checks, blank and random bytes all read as no saved lengths.
- 300 pattern loads beside the MIDI build: the same EEPROM traffic and RAM, apart from LEN, which gets the new pattern's lengths once CACHE is ready.
- Every v1.3 button gesture; setting and clearing lengths for valid and invalid slots; and 3,000 random panel ticks that match the MIDI build apart from the new state.
- Saves: with nothing marked, the main loop's saves match the MIDI build in 150 random states; marked slots are written one per save and read back (228 records); a write that doesn't stick is retried at the next 3 saves, then dropped.
- 40 random sessions of lengths set on random patterns, pattern changes and saves, then a power cycle: every pattern gets its lengths back, and no pattern byte changes.
- The light builder in 2,000 random states of every mode, playing or not, beside the MIDI build: the same lights and RAM, except the 315 states in Pattern Write with a voice of its own length selected, where the lights are exactly that voice's steps up to its length with the running light on the step it last played.

The browser checks install v1.4 on the simulated RD-6 (378 ACKs, the exact pinned stream), save its `.syx`, and refuse a modified patch before anything is sent. While it was a test build they also covered its option: unticked by default, and ticking it cleared the MIDI one and the other way round.

## How Scatter is distributed

A build is published as a patch (`outputs/scatter-v1.4.patch.json`, format `rd6-syx-replacements-v1`): a list of byte runs that replace parts of the official 1.0.5 SysEx file. The updater and `scripts/apply_patch.py` apply it on the user's computer and accept the result only if its SHA-256 matches the pinned build hash.

The repository includes Behringer's original 1.0.5 and 1.0.6 SysEx update files, mirrored without modification ([PROVENANCE.json](../firmware/PROVENANCE.json)). It does not include decrypted firmware images, device dumps, vendor service credentials or raw transfer logs. The public history starts clean; earlier research history is private.

The update file is 5 setup frames, a header and 377 data frames. The data frames carry the image XOR a repeating 128-byte mask, 7-bit packed: each group's first byte holds the top bits of the next seven bytes. The header stores the image size (bytes 10–13) and the 32-bit sum of all image bytes (bytes 14–17), each as four 7-bit digits, low digit first. The updater recovers the mask from the longest run of identical 128-byte blocks and needs at least 64. Official files have 100 or more and Scatter v1.4 keeps 85 (v1.3 kept 92, the MIDI step 90). Every build must keep at least 64.

Build a Scatter file without a browser:

```bash
python scripts/apply_patch.py firmware/RD-6_V1.0.5.syx /path/to/RD6_Scatter_v1.4.syx
```

Add `--build scatter-v1.3` for the older v1.3, or `--build scatter-v1.3-midi-test` for the MIDI step.

The script leaves the input untouched and refuses to overwrite an existing output file.

## How the updater works

### Identifying the RD-6

All messages use the RD-6 SysEx prefix `F0 00 20 32 00 01 0D 00`.

- **Version query** `… 08 F7`. Application firmware answers `… 09 00 <major> <minor> <patch> F7`.
- **Update mode** either answers `08` with an ACK (`… 01 00 00 F7`) or ignores it, as the stock bootloader examined does. The updater then sends the read-only `… 08 40 F7`, which only update mode ACKs.
- **Scatter** keeps the 1.0.5 application version, so a version reply of 1.0.5 can't tell Scatter from official 1.0.5. Scatter has a status report (below), but the updater never sends that to unknown firmware. It asks the user instead, unless it installed the firmware itself in the same session.

### Backups

The RD-6 can't read its firmware back (see [below](#why-there-is-no-real-firmware-readback)), so a backup is the official update file for the version the RD-6 reports: 1.0.6 or 1.0.5. For other versions no backup is offered, and installing Scatter needs an explicit acknowledgement. In update mode, or when the RD-6 runs Scatter, there's nothing to back up.

Backup files are JSON:

| Field | Meaning |
|---|---|
| `format` | `rd6-firmware-file-backup-v1` |
| `kind` | `official-download-not-device-dump` (older files may also say `user-supplied-file-not-device-dump`) |
| `name` | Readable name |
| `firmware` | For example `official-1.0.6` (added in this version of the updater) |
| `device_reported_version` | Version the RD-6 reported when the backup was made (added) |
| `note` | Plain explanation for anyone who opens the file (added) |
| `sha256` | SHA-256 of the SysEx file |
| `created` | Time the backup was made (ISO 8601) |
| `syx_base64` | The complete SysEx update file |

Restore files from the previous updater (`RD6_RESTORE_*.json`) use the same format without the added fields and can still be restored.

### Install and restore sequence

1. **Prepare.** Download the official file(s), apply the patch for an install, and check the result's SHA-256 against the pinned hash and its structure.
2. **Identify** the RD-6 read-only. Stop if it no longer matches what was found at Connect.
3. **Enter update mode** if the RD-6 is in application mode: confirm its version again, send `… 03 30 F7`, and watch for 15 s while the USB port disappears and comes back. If the browser doesn't see that re-enumeration, the updater confirms update mode with the read-only `08 40` before going on, and stops if the RD-6 is still in application mode.
4. **Transfer.** First `08 40`, which only update mode ACKs; if the application answers instead, nothing else is sent. Then the 5 setup frames with their exact expected replies (model, product, three ACKs), then 378 firmware frames (header and 377 data blocks).
   - One frame is in flight at a time, and each must get exactly one ACK within 2 s.
   - A timeout, NACK, duplicate, unsolicited or trailing reply aborts the transfer. There is no automatic retry.
   - After the last ACK, the updater listens for 500 ms for any trailing reply, because ACKs carry no sequence number.
   - **Stop** aborts after the current frame.
5. **Verify.** Wait 10 s for the restart, then the version reply must match the version in the file header. This confirms the RD-6 restarted into firmware with that version; it is not a flash readback.

### When Chrome loses the connection

The RD-6 drops off USB for under half a second when it switches to update mode, and again when it restarts after an update. Chrome on Windows can miss this. It then keeps the port listed as connected, but nothing sent or received gets through for as long as the page stays open. Reloading the page gives Chrome a fresh MIDI connection.

The updater treats a complete lack of replies as a lost connection when it happens before the firmware header or after the last ACK. In that case it stops and offers **Reconnect**, and it offers the same when **Connect** gets no reply at all. Reconnect saves the user's choices and the current log in `sessionStorage`, reloads the page and connects again after 2.5 s, so the old page's MIDI session has closed first. If the RD-6 is then in update mode, Install or Restore carries on without switching modes again.

Silence in the middle of the firmware is still treated as a failed transfer, with the usual advice.

### Patterns and settings

These requests come from the stock SysEx handler (1.0.5 at `0x08008404`; 1.0.6 has the same code 4 bytes later), which Scatter leaves unchanged. They only work in application mode, over USB. All use the RD-6 prefix `F0 00 20 32 00 01 0D 00`.

| Request | Reply | What it does |
|---|---|---|
| `77 gg pp` | `78 gg pp` + 44 nibbles | Reads pattern `pp` (0–15) of group `gg` (0–1): 22 bytes, sent high nibble first. Read-only. |
| `78 gg pp` + 44 nibbles | ACK `01 00 00` | Saves that pattern to the RD-6's EEPROM (64-byte slots at `index × 64`), then ACKs. |
| `75` | `76 s1 … s6` | Reads the six settings. Read-only. |
| `0E 00 s1 s2` | ACK | Sets s1 (0–15) and s2 (0–16), EEPROM `0x3082` and `0x3081`. These look like the MIDI channels. |
| `19 s3`, `1A s4`, `1B s5`, `1C s6` | ACK | Set s3 (0–1), s4 (0–3), s5 (0–3) and s6, EEPROM `0x3083`, `0x3085`, `0x3086` and `0x3084`. |

An invalid group, pattern or setting value gets a NACK (`01 01 00`). The pattern requests go through a scratch buffer (`0x20000bfc`), not the playing pattern (`0x20000a9c`) or the edit buffer. A pattern is 4 header bytes, which include its length, followed by nine 16-bit step lanes: accent and eight voices.

The backup (`rd6-patterns-settings-backup-v1`) stores each pattern as 1-based `group`/`pattern` with its 22 bytes in hex, plus the six settings and a SHA-256 over the pattern bytes in slot order followed by the settings bytes. Reading and writing follow the transfer's rules: one request at a time, exactly one expected reply, a 2 s timeout, no automatic retry, and a stop at the first unexpected reply. When restoring, patterns already saved stay saved.

### File checks and pinning

Every image is parsed before use: 383 frames, the RD-6 prefix on every frame, the setup and header commands, data block counters 0–376 in order, the unpacked size against the header, the header model strings, recovery of the XOR mask, plausible Cortex-M vectors for the GD32F350 (16 KB SRAM, 128 KB flash) and, for pinned files, the SHA-256 of the decoded image. Pinned files are official 1.0.5 and 1.0.6, Scatter v1.4, the older Scatter v1.3, the MIDI extra-hit test build, v1.2, v1 and TEST12, and two older test builds. A withdrawn test build (TEST02) is always refused. Any other structurally valid file needs the user to type the first 8 hex digits of its SHA-256.

### Simulator

**Advanced → Use a simulated RD-6** swaps in a software RD-6 that answers like the test unit did in the TEST01–TEST03 transfer logs. It can inject a NACK, a missing reply or a duplicate ACK at a chosen block, or act as a device that ignores update-mode entry. Nothing is sent to hardware.

### Run the updater locally

Web MIDI and the browser's checksum functions only work on `https://` or `http://localhost`. From the repository root:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000/outputs/rd6_webmidi_uploader.html`.

## Scatter status report

Scatter answers **CC 112, value 0** on the RD-6's MIDI receive channel with 13 MIDI messages over USB, all Polyphonic Key Pressure on channel 7 (status `A6`). The note number is the field index and the pressure value is the field. Field 0 is the build marker: 12 for every Scatter build since TEST12, v1.4 included. Fields 1–12 are layer, direction, latch, selection, active effect, pattern selector, playing, clock step, source step, last key, snapshot valid and effective direction (`source/rd6_glitch_status.ll`).

## Why there is no real firmware readback

The project examined the actual stock bootloader of the test unit. To read it, a temporary diagnostic build was installed, with the owner's permission, on a unit that already ran custom firmware; two complete reads matched. The dump and detailed analysis stay private.

That bootloader's USB update protocol has no command to read firmware, and its USB configuration exposes no standard DFU readback interface. This applies to the revision examined, not necessarily to every RD-6, and unknown commands were not tried on hardware.

The normal application firmware has no way either. Its SysEx handler was checked offline in stock 1.0.4, 1.0.5 and 1.0.6 on 2026-10-17. All 128 command values were run on both of its input paths in each version, 768 runs in all. The settings reply reads fixed RAM fields. The pattern read was run with all 128 group values and all 128 pattern values in each version, 49,152 combinations: it accepts only 2 groups and 16 patterns and returns a 22-byte pattern record. Neither read takes a flash address or a length, so neither can return firmware.

The same handler also has factory and diagnostic commands, and some of them change the device, so unknown commands weren't sent to hardware. The captured bootloader's handler was checked again offline and still has no command to read firmware. These checks can't rule out every other handler or a flaw in a parser, and they say nothing about other firmware versions. So there is still no verified way to back up the firmware itself, and a downloaded official file is not a copy of the device.

The diagnostic doesn't help with a first install either, because custom code has to be installed before it can read anything. A true backup before the first flash would need another, independently verified way in, such as hardware debugging tools.

## Verify it yourself

- **Payloads.** With Python 3.12, `pip install -r source/requirements.txt`, then `python -I source/verify_payloads.py`. This compiles the three TEST12 LLVM payloads and compares the object bytes with `source/objects.json`. It is not a full firmware rebuild or an MCU emulator.
- **Scatter v1's 1.0.6 fix.** `python -I source/check_fix106.py` reproduces the 1536 state comparisons with stock 1.0.6, using the included vendor files. Decoding stays in memory; no decrypted file is written.
- **Scatter v1.2.** `python -I source/build_scatter_v1_2.py` rebuilds the v1.2 patch from v1 and confirms it matches `source/scatter-v1.2.patch.json` byte for byte. `python -I source/check_scatter_v1_2.py` runs the step-light and Pattern Write checks described in [What v1.2 changes](#what-v12-changes). Both decode in memory only.
- **Scatter v1.3.** `python -I source/build_scatter_v1_3.py` rebuilds the patch from v1.2 and confirms it matches `source/scatter-v1.3.patch.json`. `python -I source/check_scatter_v1_3.py` runs the checks described in [What v1.3 changes](#what-v13-changes).
- **MIDI extra hits.** `python -I source/build_midi_extra.py` rebuilds the patch from v1.3 and confirms it matches `source/scatter-v1.3-midi-test.patch.json`. `python -I source/check_midi_extra.py` runs the checks described in [MIDI extra hits](#midi-extra-hits); add `--mutations` for the broken-build checks. `source/assemble_midi_extra.py` regenerates the routines' bytes and needs keystone (development only).
- **Scatter v1.4.** `python -I source/build_saved_lengths.py` rebuilds the patch from the MIDI step and confirms it matches `outputs/scatter-v1.4.patch.json`. `python -I source/check_saved_lengths.py` runs the checks described in [Saved lengths and the Pattern Write display](#saved-lengths-and-the-pattern-write-display). `source/assemble_saved_lengths.py` regenerates the routines' bytes (keystone, development only).
- **Updater.** Install Playwright and Chromium (`npm install playwright`, then `npx playwright install chromium`) and run `node outputs/check_rd6_webmidi_uploader.cjs` and `node outputs/check_rd6_automatic_workflow.cjs`. Set `RD6_CHROME_PATH` to use an installed Chrome and `RD6_SCREENSHOT_DIR` to save screenshots. Both use simulated MIDI only.

## Test results

- **TEST12 on hardware** (one RD-6, 2026-10-16, [HARDWARE_ACCEPTANCE.json](../checks/HARDWARE_ACCEPTANCE.json)). The user passed all Slice and Cut depths, straight and triplet Roll, Ratchet, hold and release, latch, effect off, every direction button, returning to Reverse after Roll, normal Play/Stop and one power cycle. The transfer had 383 byte-exact file frames and 378 firmware ACKs, and the build 12 status confirmed it was running. These are listening checks of selected paths, not laboratory timing measurements.
- **Stock round trip on hardware** (2026-10-16, previous version of the updater page, real Chrome Web MIDI). Stock 1.0.6 was restored with 383 byte-exact frames, 378 ACKs and a 1.0.6 reply after restart, and the user confirmed normal Play/Stop. TEST12 was then reinstalled the same way: status showed stopped, Scatter off and Forward, and Play/Stop and held Roll/release passed. During the stock restore Chrome missed the update-mode re-enumeration, and the read-only `08 40` check confirmed update mode before any firmware was sent. The current page keeps the same transfer engine and runs that check automatically.
- **Current updater page on hardware** (2026-10-17, Chrome 155 on Windows 10, one RD-6):
  - *Restore to official 1.0.6*, from a unit that reported 1.0.5. The first attempt hit the problem in [When Chrome loses the connection](#when-chrome-loses-the-connection). The RD-6 ACKed `03 30` twice, Chrome never reported the re-enumeration, and every later query went unanswered, including two Connect attempts a minute later. The updater stopped before any setup or firmware frame, so nothing was written. After a page reload, Connect found the RD-6 in update mode and the restore completed; the next session's identity check read 1.0.6. The Reconnect button was added in response.
  - *Scatter v1 (TEST14) install*, from official 1.0.6. Chrome saw the re-enumeration this time: the port was absent at 2.7 s and back at 3.0 s, after two entry ACKs. All 378 firmware frames were ACKed (3.2–42.1 ms each), and the trailing-reply check passed. The version query after the restart got no reply, and Reconnect was offered. After Reconnect, the RD-6 reported 1.0.5, the TEST14 header version.
- **Scatter v1**: offline checks ([TEST14_FIX106.json](../checks/TEST14_FIX106.json)). It installs and runs on hardware (see above), and was played on the test unit on 2026-10-17 with no fault found. A pattern that seemed to roll on its own turned out to be set to a length of 1. The full TEST12 listening checklist hasn't been repeated.
- **Scatter v1.2**: offline checks ([SCATTER_V1_2.json](../checks/SCATTER_V1_2.json)). Installed and played on the test unit on 2026-10-17: the step lights follow the played step, Scatter stays on through Pattern Write while the step buttons program normally there, and Scatter's controls work again back in Pattern Play.
- **Scatter v1.3**: offline checks ([SCATTER_V1_3.json](../checks/SCATTER_V1_3.json)). Installed from the public updater as the test build and played on the test unit on 2026-10-17: the user reported that mute and roll mode, the roll rates, the loop length per voice and the mode's step lights all work.
- **MIDI extra hits** (offered as a test build): offline checks ([SCATTER_MIDI_TEST.json](../checks/SCATTER_MIDI_TEST.json)) and a simulated install. Installed from a local copy of the updater on its branch and played on the test unit on 2026-10-18: the user reported that it works.
- **Scatter v1.4**: offline checks ([SCATTER_V1_4.json](../checks/SCATTER_V1_4.json)) and a simulated install. Installed from a local copy of the updater as the saved lengths test build, with the Pattern Write display, and played on the test unit on 2026-10-18: the user reported that it works great.
- **Updater, simulated**: [UPLOADER_SIMULATOR.json](../checks/UPLOADER_SIMULATOR.json) and [AUTOMATIC_WORKFLOW.json](../checks/AUTOMATIC_WORKFLOW.json).
- **Other offline checks**: `checks/RD6_SCATTER_TEST12_*.json`.

## Known technical limits

- External clock, chaining, worst-case interrupt timing and RAM liveness are unmeasured.
- An earlier fast-tempo Ratchet glitch is unresolved.
- Before v1.4, extra Roll and Ratchet hits and the 1/32 roll's second hit were analog-only: the timer interrupt that plays them can preempt the stock MIDI output queue mid-update (`source/rd6_stock_bridge_1_0_5.ll`). v1.4 serializes the queue and sends them. MIDI timing and MIDI OUT bandwidth haven't been measured.
- v1.4 writes EEPROM while patterns play, as the stock firmware does for pattern edits. Its bit-banged I2C code has no lock, so a timer's pattern load can cut into a save. Saves are read back and retried, but the timing at such a moment hasn't been measured.
- There is no flash readback, and recovery after an interrupted flash isn't guaranteed: restoring needs a working update mode.
- Offline checks run selected code paths; there is no full MCU emulation.
