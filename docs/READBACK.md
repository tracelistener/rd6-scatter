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

## TEST12 restored

After the diagnostic, the known working TEST12 file was restored. The
transmitted file was verified byte-for-byte, all firmware transactions were
acknowledged, and the post-reboot status identified TEST12, stopped with
effects off. The user also confirmed normal Play/Stop and held Roll/release after restoration.

## Restore fallback

Open your original stock `.syx` or saved restore-file JSON under **Restore
stock / saved firmware** in the uploader. Confirm the file is saved, stop
playback, enter update mode and choose **Restore selected firmware**.

The complete stock-file transfer path passed simulator checks. On 2026-10-16,
the actual browser uploader also restored stock1.0.6 on the test unit, with
383 byte-exact file frames,378 firmware ACKs and a1.0.6 post-reboot reply.
The user confirmed normal stock Play/Stop. TEST12 was then reinstalled through the browser with383 byte-exact file frames,378 firmware ACKs and build12 status showing stopped, Scatter off and Forward. The final post-round-trip Roll listening check is pending. The earlier return
from the diagnostic to TEST12 was verified. Restore still requires a working update interface,
so it is not guaranteed brick recovery. Saving a supplied file remains a
file copy, not a backup read from the device. See
[restore instructions](BACKUP_RESTORE.md).
