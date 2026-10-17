# RD-6 Scatter

Four held performance effects for the Behringer RD-6: **Roll, Ratchet, Slice and Cut**, with independent Forward, Reverse, Random and Ping-pong playback directions. Experimental firmware. TEST12 was tested on one RD-6; TEST14 adds an offline-checked stock1.0.6 fix.

**[Open the browser uploader](https://tracelistener.github.io/rd6-scatter/)** · [Controls](docs/CONTROLS.md) · [Backup and restore](docs/BACKUP_RESTORE.md) · [Checks](checks/HARDWARE_ACCEPTANCE.json)

## Download and install — no firmware files needed

1. Open the uploader in desktop Chrome or Edge and choose **Download firmware and save restore copy**.
2. The tool downloads verified official stock **1.0.6 for restoration** and **1.0.5 for the Scatter patch**. It requests a download of a checksummed stock1.0.6 restore JSON. Locate that file and confirm it is saved.
3. Choose a build and **Prepare Scatter locally**. Keep the prepared SysEx file too.
4. Stop playback, connect USB and close other MIDI applications. Request MIDI/SysEx access, query identity, then enter update mode.
5. Acknowledge the transfer and send firmware. Keep power, USB and the tab active until the reboot check finishes.

The original vendor SysEx update packages are mirrored in `firmware/`, with source and checksums in [PROVENANCE.json](firmware/PROVENANCE.json). No decrypted BIN images, device dumps or vendor service credentials are distributed. Downloads and patching need no MIDI access and send nothing to the RD-6.

### Which build?

- **TEST14_FIX106:** TEST12's effects and controls plus a backport of the documented stock1.0.6 pattern-group selection fix. It passed offline instruction checks; **physical TEST14 testing is pending**. This is not a full port onto stock1.0.6: application version remains1.0.5 and the diagnostic marker remains12.
- **TEST12_GLITCH:** the original hardware-tested build, available as an option. It does not contain that1.0.6 fix.

The [1.0.6 fix](https://mediadl.musictribe.com/download/software/behringer/RD6/Release-Notes_BE_RD-6_v1-0-6_Rev.1.pdf) preserves a selected pattern number when changing its pattern group during playback, even if the number was chosen first. TEST14's actual saved Thumb code matched stock1.0.6 in1536 state comparisons; see [build checks](checks/TEST14_FIX106.json).

### Restore stock1.0.6

Choose **Select stock 1.0.6 for restore** in section 1. It selects/downloads the verified stock file without a file chooser. Locate the saved restore copy and confirm it is saved. Stop playback, enter update mode if needed, then use **Restore selected firmware** in section 3. Entering update mode does not itself start restoration. If the RD-6 is already in update mode, use Identity query to confirm it and continue directly to section 3; do not enter again. Saved JSON and original SysEx import remain available under **Restore or use your own files**. The tool checks the checksum, file structure, every transfer acknowledgement and the post-reboot version.

The restore file is a vendor update, **not a readback of your installed firmware**. It does not include the bootloader, patterns or settings. Stock-first USB firmware readback remains unavailable on the revision investigated. Restoration requires a working update interface; it is not guaranteed interrupted-flash recovery. [Backup and restore details](docs/BACKUP_RESTORE.md).

To run locally, clone/download the repository, run `python -m http.server 8000` in its root, and open `http://localhost:8000/outputs/rd6_webmidi_uploader.html`. A simulator is included and opens no MIDI ports.

## Play

In PATTERN PLAY while playing, hold FUNCTION and press TAP to enter Scatter. Release both; a fresh TAP holds the selected effect, and release resumes the running pattern unless latched.

| Effects | | | |
|---|---|---|---|
| **1** Roll | **2** Ratchet | **3** Slice | **4** Cut |
| **5** Depth1 | **6** Depth2 | **7** Depth3 | **8** Depth4 |
| **9** Forward | **10** Reverse | **11** Random | **12** Ping-pong |
| **13** Straight Roll | **14** Triplet Roll | **15** Latch | **16** Effect off |

PATTERN GROUP duplicates Step15's latch. Step16 cancels latch and held TAP until TAP is released and pressed again. Stop exits Scatter, turns effects off and restores Forward. Reverse starts at the **next bar**, then reads16→1 including rests. Step LEDs retain the underlying clock display.

Roll repeats captured hits/chords; Ratchet repeats programmed hits; Slice makes scripted step jumps/repeats/reversed fragments; Cut skips triggers in rhythmic patterns. Cut leaves existing analog decays sounding. Roll and extra Ratchet hits are analog-only: listen to the RD-6 audio output.

## Validation and limits

On the test unit, the user passed all Slice/Cut depths, Roll straight/triplet, Ratchet, hold/release, latch, effect-off, all direction buttons, returning to Reverse after Roll, normal Play/Stop and one power cycle. The transfer had378 firmware ACKs and 383 byte-exact transmitted file frames; build12 status confirmed execution. These are listening/selected-path checks, not laboratory timing measurements.

External clock/chain, worst-case interrupt timing and RAM liveness remain unmeasured. An earlier fast-tempo Ratchet glitch remains unresolved/deferred. USB-only restoration is not guaranteed. The browser transfer engine passed 22 simulator checks, and the actual browser uploader restored stock 1.0.6 on the test unit with 378 ACKs and a matching post-reboot version reply. The user confirmed normal stock Play/Stop. TEST12 was then reinstalled through the browser with 383 byte-exact file frames, 378 firmware ACKs and build12 status showing stopped, Scatter off and Forward. The user also confirmed normal TEST12 Play/Stop and held Roll/release after the round trip.

## Source and development

`source/` contains our LLVM core, panel, status, bridge/timer sources and the TEST14 backport. `outputs/TEST12.patch.json` and `outputs/TEST14.patch.json` contain changed byte runs against the pinned stock1.0.5 SysEx. Original vendor SysEx containers are provided for automatic preparation/restoration; decrypted images and raw device logs remain private.

Prepare a file without a browser: `python scripts/apply_patch.py firmware/RD-6_V1.0.5.syx /path/to/Scatter.syx --build test14`. Use `--build test12` for the earlier build. This preserves the input and refuses to overwrite an existing output.

Verify compilation of the three TEST12 payloads with Python3.12: install `source/requirements.txt`, then run `python -I source/verify_payloads.py`. This verifies our payload objects; it is not a full firmware rebuild or full MCU emulator. Run `python -I source/check_fix106.py` to independently reproduce the1536 stock1.0.6 backport comparisons using the included vendor SysEx containers. Decoding stays in memory; no decrypted firmware file is written.

Browser checks: install Playwright and Chromium, then run `node outputs/check_rd6_webmidi_uploader.cjs` and `node outputs/check_rd6_automatic_workflow.cjs`. The repository includes their input files. Optionally set `RD6_CHROME_PATH` to a Chrome executable. These checks use simulated MIDI only.

This is an independent experiment, not a Behringer or Roland product. Original vendor SysEx update files are mirrored without modification; vendor ownership is unchanged. The public repository starts with a clean history; the earlier research history remains private.
