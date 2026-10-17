# Stock firmware backup before first install

**Automatic firmware backup from an untouched stock RD-6 remains unavailable.**

The investigation now includes the actual stock bootloader from our test
unit, rather than just the application update files. A temporary diagnostic
was installed on the already-custom unit with the user's permission. Two
complete bootloader reads matched. The dump and detailed analysis stay private.

The captured bootloader's normal USB update protocol does not implement a
firmware-read command, and its USB configuration does not expose a standard
DFU readback interface. This conclusion applies to the revision examined,
not every possible RD-6 revision or every possible vulnerability. Unknown
commands were not probed on hardware.

The diagnostic does not solve first-install backup: custom code must be
installed before it can read anything. Another independently verified access
method would be needed for a true backup before the first flash.

## Application dispatcher cross-check — 2026-10-17

The normal SysEx application dispatcher was checked offline in stock1.0.4,
1.0.5 and1.0.6. All128 legal command selections were executed on both input
paths for each version (768 family selections). The settings reply reads
fixed RAM fields. The pattern-read handler was checked with all128 bank
values and all128 pattern values in each version (49,152 combinations): it
accepts only2 banks and16 patterns and returns22 pattern-record bytes.
Neither read path accepts a flash address or a firmware length.

The factory/diagnostic family also contains mutating operations, so unknown
commands were not sent to hardware. The captured bootloader dispatcher was
rechecked offline and still exposes no normal firmware-read command.
These checks do not prove absence of every alternate handler or exploitable
parser flaw, and cannot establish support across arbitrary firmware versions.
There remains no verified stock-first firmware readback feature to add to
the uploader. A downloaded vendor restore package is not a device backup.

## TEST12 restored

After the diagnostic, the known working TEST12 file was restored. The
transmitted file was verified byte-for-byte, all firmware transactions were
acknowledged, and the post-reboot status identified TEST12, stopped with
effects off. The user also confirmed normal Play/Stop and held Roll/release after restoration.

## Restore fallback

Use **Download firmware and save restore copy** to obtain stock1.0.6 without supplying a file. To restore, open the downloaded JSON under **Restore stock / saved firmware** in the uploader. Confirm the file is saved, stop
playback, enter update mode and choose **Restore selected firmware**.

The complete stock-file transfer path passed simulator checks. On 2026-10-16,
the actual browser uploader also restored stock 1.0.6 on the test unit, with
383 byte-exact file frames, 378 firmware ACKs and a 1.0.6 post-reboot reply.
The user confirmed normal stock Play/Stop. TEST12 was then reinstalled through the browser with 383 byte-exact file frames, 378 firmware ACKs and build12 status showing stopped, Scatter off and Forward. The user also confirmed normal TEST12 Play/Stop and held Roll/release after the round trip. The earlier return
from the diagnostic to TEST12 was verified. Restore still requires a working update interface,
so it is not guaranteed brick recovery. Saving a supplied file remains a
file copy, not a backup read from the device. See
[restore instructions](BACKUP_RESTORE.md).
