# Technical notes

For people who want to know how Scatter and the updater work, or check them. Players only need the [README](../README.md).

## Repository layout

| Path | Contents |
|---|---|
| `index.html` | Sends the GitHub Pages site to the updater |
| `outputs/rd6_webmidi_uploader.html` | The updater: one self-contained page |
| `outputs/scatter-v1.2.patch.json` | Scatter v1.2 as byte replacements on the official 1.0.5 update file |
| `outputs/scatter-v1.3-test.patch.json` | The v1.3 test build, the same way |
| `outputs/check_*.cjs` | Browser checks for the updater (simulated MIDI only) |
| `firmware/` | Behringer's official 1.0.5 and 1.0.6 SysEx update files, unmodified. Source and checksums: `PROVENANCE.json` |
| `scripts/apply_patch.py` | Builds a Scatter `.syx` from the official 1.0.5 file without a browser |
| `source/` | Scatter source (LLVM IR), the 1.0.6-fix backport, the v1.2 changes, the older v1 and TEST12 patches that v1.2 is built from, and offline verification scripts |
| `checks/` | Recorded results of offline, simulator and hardware checks |
| `docs/` | User guides and these notes |

## Builds

**Scatter v1.2** is the only build the updater offers. SysEx SHA-256: `8bbc359ebdf78357f7233556bf2843d53b34e8a1a52a4f1c0b8b83a9db9d41dc`. It was built in two steps:

1. **Scatter v1** (`2cdce8d2ae225feb21a153d69669c3406410893e9d1882ac0c8fb5391468b97b`), developed as `TEST14_FIX106`: the hardware-tested `TEST12_GLITCH` (`9bc1c3a74da476c6694724314d275030a7debb4299c561d06cf56f4e55b540ef`) plus a backport of the 1.0.6 pattern-group fix.
2. **Scatter v1.2**: v1 plus step lights that follow the played step, and Scatter staying on in Pattern Write ([below](#what-v12-changes)).

The v1 and TEST12 patches stay in `source/` only so that v1.2 can be rebuilt from v1, and so the checks can confirm exactly what each step changes. The updater still recognises a v1 or TEST12 file as an older Scatter build.

Scatter is a patch on official firmware **1.0.5** and reports application version 1.0.5. Behringer's newest firmware is **1.0.6**. Scatter is not a port onto 1.0.6: v1 adds only the documented 1.0.6 fix (keeping a queued pattern number when the pattern group changes during playback) to TEST12, as a 4-byte hook and a 22-byte routine. Its saved Thumb code matched stock 1.0.6 in all 1536 state comparisons of `source/check_fix106.py`, and the effect, panel, timer and startup bytes are unchanged from TEST12 ([checks/TEST14_FIX106.json](../checks/TEST14_FIX106.json)). The diagnostic build marker is still 12 in v1 and v1.2.

### What v1.2 changes

Built from the v1 patch by `source/build_scatter_v1_2.py` and checked by `source/check_scatter_v1_2.py` ([results](../checks/SCATTER_V1_2.json)). It is Scatter v1 plus two changes, each a short branch to new code below `0x0800CE00`.

**Step lights follow the played step** (`source/step_lights.py`). The stock light builder (`0x0800641C`) draws the running step light from the clock step, read at `0x080064EA` (`ldrb.w r2, [r8, #8]`, where r8 is the transport at `0x20000BB4`). That instruction now calls a 60-byte routine at `0x0800CD90`. The routine reads Scatter's direction snapshot at `0x20002070`, which holds the clock step, the pattern length, the played step and a `0xD1000000` tag. It returns the played step when the snapshot is tagged, matches the current clock step and pattern length, and lies inside the pattern. Otherwise it returns the clock step, exactly as stock. Scatter's step hook writes the snapshot every step and clears it when playback stops or Scatter's direction resets, so outside Scatter the lights behave as before. This change was first tried as a v1.1 test build: the first attempt read `0x20001970` by mistake, and after the fix the lights were confirmed on the test unit.

**Scatter stays on in Pattern Write** (`source/mode_keep.py`). In v1, two checks reset Scatter whenever the mode byte (`0x20000260`) isn't 2 (Pattern Play): the panel tick cancels the layer (`0x0800BF14`), and the direction check clears the direction (`0x0800CCF6`). In v1.2, mode 3 (Pattern Write) while playing keeps the layer and the direction, and the panel handles no Scatter buttons, so the RD-6's own Write controls work. Stopping, a busy panel, START/STOP and every other mode still reset Scatter exactly as in v1.

The check runs the light routine in `source/rd6_thumb_machine.py` from its real call site over 4,794 state combinations. It runs the panel and direction decisions in both v1 and v1.2 for all 84 combinations of mode, playing, busy and START/STOP. It also confirms that v1.2 differs from v1 only at the three call sites and in the three new routines. Both changes were confirmed on the test unit on 2026-10-17.

### Scatter v1.3 test build

SysEx SHA-256 `ff0bb9d18ae7d926f780a65dddda53cb925cb544d3c46a2d5ae1472ff7848fc5`. Scatter v1.2 plus a mute and roll mode modelled on the Quicksilver 606's, and a loop length per voice ([controls](CONTROLS.md#mute-and-roll-mode-v13-test-build)). The updater offers it as an unticked option under Install. It hasn't been tested on hardware yet.

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

## How Scatter is distributed

A build is published as a patch (`outputs/scatter-v1.2.patch.json`, format `rd6-syx-replacements-v1`): a list of byte runs that replace parts of the official 1.0.5 SysEx file. The updater and `scripts/apply_patch.py` apply it on the user's computer and accept the result only if its SHA-256 matches the pinned build hash.

The repository includes Behringer's original 1.0.5 and 1.0.6 SysEx update files, mirrored without modification ([PROVENANCE.json](../firmware/PROVENANCE.json)). It does not include decrypted firmware images, device dumps, vendor service credentials or raw transfer logs. The public history starts clean; earlier research history is private.

The update file is 5 setup frames, a header and 377 data frames. The data frames carry the image XOR a repeating 128-byte mask, 7-bit packed: each group's first byte holds the top bits of the next seven bytes. The header stores the image size (bytes 10–13) and the 32-bit sum of all image bytes (bytes 14–17), each as four 7-bit digits, low digit first. The updater recovers the mask from the longest run of identical 128-byte blocks and needs at least 64. Official files have 100 or more, and the v1.3 test build keeps 92, so new code must not break up that run any further.

Build a Scatter file without a browser:

```bash
python scripts/apply_patch.py firmware/RD-6_V1.0.5.syx /path/to/RD6_Scatter_v1.2.syx
```

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

Every image is parsed before use: 383 frames, the RD-6 prefix on every frame, the setup and header commands, data block counters 0–376 in order, the unpacked size against the header, the header model strings, recovery of the XOR mask, plausible Cortex-M vectors for the GD32F350 (16 KB SRAM, 128 KB flash) and, for pinned files, the SHA-256 of the decoded image. Pinned files are official 1.0.5 and 1.0.6, Scatter v1.2, the v1.3 test build, the older Scatter v1 and TEST12, and two older test builds. A withdrawn test build (TEST02) is always refused. Any other structurally valid file needs the user to type the first 8 hex digits of its SHA-256.

### Simulator

**Advanced → Use a simulated RD-6** swaps in a software RD-6 that answers like the test unit did in the TEST01–TEST03 transfer logs. It can inject a NACK, a missing reply or a duplicate ACK at a chosen block, or act as a device that ignores update-mode entry. Nothing is sent to hardware.

### Run the updater locally

Web MIDI and the browser's checksum functions only work on `https://` or `http://localhost`. From the repository root:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000/outputs/rd6_webmidi_uploader.html`.

## Scatter status report

Scatter answers **CC 112, value 0** on the RD-6's MIDI receive channel with 13 MIDI messages over USB, all Polyphonic Key Pressure on channel 7 (status `A6`). The note number is the field index and the pressure value is the field. Field 0 is the build marker: 12 for Scatter v1.2, as for v1 and TEST12. Fields 1–12 are layer, direction, latch, selection, active effect, pattern selector, playing, clock step, source step, last key, snapshot valid and effective direction (`source/rd6_glitch_status.ll`).

## Why there is no real firmware readback

The project examined the actual stock bootloader of the test unit. To read it, a temporary diagnostic build was installed, with the owner's permission, on a unit that already ran custom firmware; two complete reads matched. The dump and detailed analysis stay private.

That bootloader's USB update protocol has no command to read firmware, and its USB configuration exposes no standard DFU readback interface. This applies to the revision examined, not necessarily to every RD-6, and unknown commands were not tried on hardware.

The normal application firmware has no way either. Its SysEx handler was checked offline in stock 1.0.4, 1.0.5 and 1.0.6 on 2026-10-17. All 128 command values were run on both of its input paths in each version, 768 runs in all. The settings reply reads fixed RAM fields. The pattern read was run with all 128 group values and all 128 pattern values in each version, 49,152 combinations: it accepts only 2 groups and 16 patterns and returns a 22-byte pattern record. Neither read takes a flash address or a length, so neither can return firmware.

The same handler also has factory and diagnostic commands, and some of them change the device, so unknown commands weren't sent to hardware. The captured bootloader's handler was checked again offline and still has no command to read firmware. These checks can't rule out every other handler or a flaw in a parser, and they say nothing about other firmware versions. So there is still no verified way to back up the firmware itself, and a downloaded official file is not a copy of the device.

The diagnostic doesn't help with a first install either, because custom code has to be installed before it can read anything. A true backup before the first flash would need another, independently verified way in, such as hardware debugging tools.

## Verify it yourself

- **Payloads.** With Python 3.12, `pip install -r source/requirements.txt`, then `python -I source/verify_payloads.py`. This compiles the three TEST12 LLVM payloads and compares the object bytes with `source/objects.json`. It is not a full firmware rebuild or an MCU emulator.
- **Scatter v1's 1.0.6 fix.** `python -I source/check_fix106.py` reproduces the 1536 state comparisons with stock 1.0.6, using the included vendor files. Decoding stays in memory; no decrypted file is written.
- **Scatter v1.2.** `python -I source/build_scatter_v1_2.py` rebuilds the v1.2 patch from v1 and confirms it matches `outputs/scatter-v1.2.patch.json` byte for byte. `python -I source/check_scatter_v1_2.py` runs the step-light and Pattern Write checks described in [What v1.2 changes](#what-v12-changes). Both decode in memory only.
- **Scatter v1.3 test build.** `python -I source/build_scatter_v1_3.py` rebuilds the patch from v1.2 and confirms it matches `outputs/scatter-v1.3-test.patch.json`. `python -I source/check_scatter_v1_3.py` runs the checks described in [Scatter v1.3 test build](#scatter-v13-test-build).
- **Updater.** Install Playwright and Chromium (`npm install playwright`, then `npx playwright install chromium`) and run `node outputs/check_rd6_webmidi_uploader.cjs` and `node outputs/check_rd6_automatic_workflow.cjs`. Set `RD6_CHROME_PATH` to use an installed Chrome and `RD6_SCREENSHOT_DIR` to save screenshots. Both use simulated MIDI only.

## Test results

- **TEST12 on hardware** (one RD-6, 2026-10-16, [HARDWARE_ACCEPTANCE.json](../checks/HARDWARE_ACCEPTANCE.json)). The user passed all Slice and Cut depths, straight and triplet Roll, Ratchet, hold and release, latch, effect off, every direction button, returning to Reverse after Roll, normal Play/Stop and one power cycle. The transfer had 383 byte-exact file frames and 378 firmware ACKs, and the build 12 status confirmed it was running. These are listening checks of selected paths, not laboratory timing measurements.
- **Stock round trip on hardware** (2026-10-16, previous version of the updater page, real Chrome Web MIDI). Stock 1.0.6 was restored with 383 byte-exact frames, 378 ACKs and a 1.0.6 reply after restart, and the user confirmed normal Play/Stop. TEST12 was then reinstalled the same way: status showed stopped, Scatter off and Forward, and Play/Stop and held Roll/release passed. During the stock restore Chrome missed the update-mode re-enumeration, and the read-only `08 40` check confirmed update mode before any firmware was sent. The current page keeps the same transfer engine and runs that check automatically.
- **Current updater page on hardware** (2026-10-17, Chrome 155 on Windows 10, one RD-6):
  - *Restore to official 1.0.6*, from a unit that reported 1.0.5. The first attempt hit the problem in [When Chrome loses the connection](#when-chrome-loses-the-connection). The RD-6 ACKed `03 30` twice, Chrome never reported the re-enumeration, and every later query went unanswered, including two Connect attempts a minute later. The updater stopped before any setup or firmware frame, so nothing was written. After a page reload, Connect found the RD-6 in update mode and the restore completed; the next session's identity check read 1.0.6. The Reconnect button was added in response.
  - *Scatter v1 (TEST14) install*, from official 1.0.6. Chrome saw the re-enumeration this time: the port was absent at 2.7 s and back at 3.0 s, after two entry ACKs. All 378 firmware frames were ACKed (3.2–42.1 ms each), and the trailing-reply check passed. The version query after the restart got no reply, and Reconnect was offered. After Reconnect, the RD-6 reported 1.0.5, the TEST14 header version.
- **Scatter v1**: offline checks ([TEST14_FIX106.json](../checks/TEST14_FIX106.json)). It installs and runs on hardware (see above), and was played on the test unit on 2026-10-17 with no fault found. A pattern that seemed to roll on its own turned out to be set to a length of 1. The full TEST12 listening checklist hasn't been repeated.
- **Scatter v1.2**: offline checks ([SCATTER_V1_2.json](../checks/SCATTER_V1_2.json)). Installed and played on the test unit on 2026-10-17: the step lights follow the played step, Scatter stays on through Pattern Write while the step buttons program normally there, and Scatter's controls work again back in Pattern Play.
- **Scatter v1.3 test build**: offline checks ([SCATTER_V1_3.json](../checks/SCATTER_V1_3.json)) and a simulated install. Not yet tested on hardware.
- **Updater, simulated**: [UPLOADER_SIMULATOR.json](../checks/UPLOADER_SIMULATOR.json) and [AUTOMATIC_WORKFLOW.json](../checks/AUTOMATIC_WORKFLOW.json).
- **Other offline checks**: `checks/RD6_SCATTER_TEST12_*.json`.

## Known technical limits

- External clock, chaining, worst-case interrupt timing and RAM liveness are unmeasured.
- An earlier fast-tempo Ratchet glitch is unresolved.
- Extra Roll and Ratchet hits are analog-only. The timer interrupt that plays them can preempt the stock MIDI output queue mid-update, so extra-hit MIDI stays disabled (`source/rd6_stock_bridge_1_0_5.ll`).
- There is no flash readback, and recovery after an interrupted flash isn't guaranteed: restoring needs a working update mode.
- Offline checks run selected code paths; there is no full MCU emulation.
