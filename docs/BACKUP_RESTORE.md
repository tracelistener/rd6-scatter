# Backup and restore

## What the uploader saves

Choose **Download firmware and save restore copy**. The uploader fetches verified official stock1.0.6 and1.0.5 from the project's mirror and requests a download of a stock1.0.6 restore JSON. Locate it and confirm it is saved before preparing Scatter. No firmware file needs to be supplied by the user.

The JSON contains the complete unmodified vendor1.0.6 SysEx update, its SHA-256 and a label identifying a vendor download rather than a device dump. It can be reimported through the restore file chooser. **Save restore copy again** repeats the download if necessary. Optional file import remains available for existing backups.
There is no verified USB firmware-readback command in this project. It cannot read the installed firmware from your RD-6. File backup is not a full-flash dump, does not include the bootloader or saved patterns/settings, and cannot verify that your selected file equals the currently installed firmware. Back up patterns/settings separately with an appropriate vendor workflow.

## Restore a saved file

1. Open the uploader and choose your saved JSON under **Restore a saved backup**, or supply the original `.syx` there.
2. The tool verifies its checksum, framing and firmware structure. Confirm your backup is saved.
3. Stop playback, connect USB, query identity and enter update mode normally.
4. Review the loaded file's name/hash, acknowledge the transfer and choose **Restore selected firmware**. The transfer is logged as `restore`.

The known stock 1.0.5 and 1.0.6 files are recognized automatically. After transfer, the application reply must match the selected file header version. Preparation automatically downloads stock1.0.5 as the patch input and keeps stock1.0.6 separately for restoration. TEST14 backports the documented1.0.6 pattern-group fix; it is not a full1.0.6 port and has not yet passed physical testing. An unpinned structurally valid firmware file requires the existing typed hash confirmation. A damaged backup is rejected and cannot retain authority from a previously selected file.

Restoration uses the same write protocol as installation. It depends on a working application/update interface; it is not a promise of recovery after an interrupted flash. Do not keep retrying a partial update blindly. A full MCU backup/recovery would require separately verified hardware debugging access and tools.

## Public distribution

The public repository includes original vendor1.0.5/1.0.6 SysEx update containers and our Scatter patches. Decrypted `.bin` images, device dumps, service credentials and raw transfer logs remain private. See `firmware/PROVENANCE.json` for source and checksums.

The full stock-file restore path is covered by a simulated transfer test, including 378 ACKs, byte-exact stock frames and post-transfer application response. On 2026-10-16, the actual browser uploader restored stock 1.0.6 on the test unit: all 383 file frames matched, 378 firmware transactions were acknowledged, and the application reported1.0.6 after reboot. The user confirmed normal stock Play/Stop. TEST12 was then reinstalled through the same browser uploader, verified by its build12 status, and passed normal Play/Stop and held Roll/release. This does not establish brick recovery.
