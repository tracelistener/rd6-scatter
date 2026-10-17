# Backup and restore

## What the uploader saves

Select a firmware `.syx` file you already possess, then choose **Download restore-file backup**. The downloaded JSON contains that exact file, its SHA-256 and a label stating that it is a user-supplied file copy. Save it somewhere you can find later. The tool does not send your file to a server.

There is no verified USB firmware-readback command in this project. It cannot read the installed firmware from your RD-6. File backup is not a full-flash dump, does not include the bootloader or saved patterns/settings, and cannot verify that your selected file equals the currently installed firmware. Back up patterns/settings separately with an appropriate vendor workflow.

## Restore a saved file

1. Open the uploader and choose your saved JSON under **Restore a saved backup**, or supply the original `.syx` there.
2. The tool verifies its checksum, framing and firmware structure. Confirm your backup is saved.
3. Stop playback, connect USB, query identity and enter update mode normally.
4. Review the loaded file's name/hash, acknowledge the transfer and send it.

The known stock1.0.5 file is recognized automatically. An unpinned structurally valid firmware file requires the existing typed hash confirmation. A damaged backup is rejected and cannot retain authority from a previously selected file.

Restoration uses the same write protocol as installation. It depends on a working application/update interface; it is not a promise of recovery after an interrupted flash. Do not keep retrying a partial update blindly. A full MCU backup/recovery would require separately verified hardware debugging access and tools.

## Public distribution

Full `.bin`/`.syx` images, private backups and raw transfer logs are excluded from the public repository and its history. The browser fetches only the TEST12 patch; the user supplies the stock file locally. Keep your downloaded restore files private.
