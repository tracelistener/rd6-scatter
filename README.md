# RD-6 Scatter — TEST12

Four held performance effects for the Behringer RD-6: **Roll, Ratchet, Slice and Cut**, with independent Forward, Reverse, Random and Ping-pong playback directions. Experimental firmware, tested on one RD-6 with application version 1.0.5.

**[Open the browser uploader](https://tracelistener.github.io/rd6-scatter/)** · [Controls](docs/CONTROLS.md) · [Backup and restore](docs/BACKUP_RESTORE.md) · [Checks](checks/HARDWARE_ACCEPTANCE.json)

## Automatic stock-firmware backup is not implemented

Investigation of the actual stock bootloader found no firmware-read command in its normal USB update protocol on the revision tested. The uploader cannot read the installed firmware from untouched stock. Detailed firmware analysis stays private. Saving a
file you supply is only a file copy. If you need a device-read backup before
the first flash, this tool does not yet meet that requirement. See
[readback investigation](docs/READBACK.md).

## Install

This repository distributes a **patch and our source**, not complete stock/modified firmware images or decrypted firmware. Supply your own **stock RD-6 1.0.5 `.syx` file**. The uploader checks its SHA-256, applies the patch locally and verifies that the result matches the tested TEST12 file. Files stay in your browser; only the patch is fetched from this site.

1. Open the uploader in desktop Chrome or Edge. Choose your original firmware file.
2. Download the checksummed restore-file backup, locate it on your computer and confirm it is saved.
3. Choose **Prepare TEST12 locally**. Keep the prepared `.syx` file too.
4. Stop playback, connect USB and close other MIDI applications. Request MIDI/SysEx access, query identity, then enter update mode.
5. Confirm the transfer acknowledgement and send the firmware. Keep power, USB and this tab active through the reboot check.

The uploader cannot dump installed firmware over USB. Its backup is a copy of a firmware file you supply, **not a device/full-flash backup**, and does not save patterns/settings. Restoration requires a responsive update interface; saving a stock file does not guarantee recovery from a failed update.

To run locally, clone/download this repo, run `python -m http.server 8000` in its root, then open `http://localhost:8000/outputs/rd6_webmidi_uploader.html`. No dependencies are needed for the uploader. A simulator is included and opens no MIDI ports.

## Restore stock firmware

Under **Restore stock / saved firmware**, open your original stock 1.0.5 or1.0.6
`.syx` or the saved restore-file JSON. Confirm it is saved, stop playback,
enter update mode, then choose **Restore selected firmware**. The file is
validated and transmitted with the same ACK pacing as installation.
This requires a functioning update interface; it is not automatic backup
or guaranteed recovery from an interrupted flash.

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

`source/` contains our TEST12 LLVM core, panel, status and earlier bridge/timer sources. No full firmware or device dumps are committed. `outputs/TEST12.patch.json` contains only changed byte runs against the pinned user-supplied SysEx, including the established startup/hooks.

Prepare a file without a browser: `python scripts/apply_patch.py /path/to/your/stock.syx /path/to/TEST12.syx`. This preserves the input and refuses to overwrite an existing output.

Verify compilation of the three TEST12 payloads with Python3.12: install `source/requirements.txt`, then run `python -I source/verify_payloads.py`. This verifies our payload objects; it is not a full firmware rebuild or full MCU emulator.

Browser regression tests: install Playwright and its Chromium, set `RD6_STOCK_SYX` to your own stock 1.0.5 file, then run `node outputs/check_rd6_webmidi_uploader.cjs`. Set `RD6_STOCK_106_SYX` to your own stock 1.0.6 file to include the full 22-check restore/reinstall suite. Optionally set `RD6_CHROME_PATH` to a Chrome executable. Tests use only the simulated RD-6.

This is an independent experiment, not a Behringer or Roland product. Original vendor firmware is not distributed here. The public repository starts with a clean history; the earlier research history remains private.
