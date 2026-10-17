# Backup, restore and troubleshooting

## Firmware backup

The RD-6 has no way to send its firmware back to a computer over USB, so the updater can't copy what's on your RD-6. (On the unit examined for this project, the update mode has no read command at all. See the [technical notes](TECHNICAL.md#why-there-is-no-real-firmware-readback).)

What the updater does instead:

1. When you click **Connect**, it asks the RD-6 which firmware version it runs. This only reads; nothing on the RD-6 changes.
2. **Save backup** downloads Behringer's official update file for that version and saves it on your computer as `RD6_BACKUP_official-<version>_<date>.json`.
3. Restoring that file writes the same official firmware back to the RD-6.

| Your RD-6 reports | Your backup |
|---|---|
| **1.0.6** | Official firmware 1.0.6 |
| **1.0.5** | Scatter reports 1.0.5 too, so the updater asks which one you have. **Official 1.0.5** (or not sure): the backup is official 1.0.5. **Scatter**: there's nothing to back up, because you can reinstall Scatter at any time. |
| **Any other version** | No backup is possible, because the updater has no copy of that version. It asks you to confirm before installing Scatter. You can still restore official 1.0.6 later, or install Behringer's newest firmware with their SynthTribe app. |
| **Update mode** (waiting for firmware) | Nothing to back up, because the firmware on it can't be identified. Install and Restore still work. |

**What a firmware backup doesn't include:** your patterns and settings (save those separately, see below) and the RD-6's bootloader (the small built-in program that installs updates).

**Is it exactly what's on my RD-6?** It's Behringer's official update for the version your RD-6 reports, so restoring it gives you that official version. The updater can't compare it byte for byte with your RD-6's memory, because it can't read that memory.

## Patterns and settings backup

Unlike the firmware, patterns and settings can be read from the RD-6. **Save patterns and settings** (in the Back up step) reads all 32 patterns (2 groups of 16) and the RD-6's six settings, such as its MIDI channels. It saves them as `RD6_PATTERNS_<date>.json`. Reading doesn't change anything on the RD-6. Press STOP first.

The RD-6 keeps patterns and settings in a separate memory from the firmware, so installing Scatter or restoring firmware doesn't change them. A copy is still worth having before you update.

To restore them, choose **Restore → Patterns and settings from a file**, pick the file and click **Restore patterns and settings**. This replaces all 32 patterns and the settings on the RD-6, and doesn't touch the firmware. The RD-6 has to be running normally, not in update mode. The updater checks the file's checksum first and refuses edited or damaged files.

## Restore

### Official firmware 1.0.6 (no file needed)

1. Open the [updater](https://tracelistener.github.io/rd6-scatter/). Connect the RD-6 by USB and press STOP.
2. Click **Connect**.
3. Choose **Restore**, then **Official firmware 1.0.6**.
4. Click **Restore official firmware 1.0.6** and wait until the updater says **Done**.

### Firmware from your backup file

Do the same, but choose **Firmware from a file** and pick your `RD6_BACKUP_….json` file, then click **Restore firmware from file**.

The updater checks the file before using it and refuses damaged files. These also work:

- restore files saved by the previous version of the updater (`RD6_RESTORE_….json`)
- Behringer's `.syx` update files for 1.0.5 and 1.0.6
- Scatter `.syx` files saved from the updater

To use any other firmware file, you have to confirm it by typing the first 8 characters of its checksum. Only do that if you know where the file came from.

### If your RD-6 is already in update mode

**Connect** recognises update mode, and Install and Restore then skip the mode switch. You don't need to do anything differently.

## If something goes wrong

**"Chrome lost its connection to your RD-6"**
When the RD-6 switches to update mode or restarts, it drops off USB for a moment. Chrome sometimes doesn't notice, and after that nothing gets through to the RD-6. The updater stops before writing anything when this happens. Click **Reconnect**: the page reloads, keeps your choices and connects again. Then click Install or Restore to carry on. If it still can't reach the RD-6, close any other browser tabs that use MIDI devices and click **Reconnect** again.

**"No RD-6 found"**
Check the USB cable and that the RD-6 is switched on. Close SynthTribe, your DAW and any other music software (on Windows, only one program can use a MIDI device at a time). Then click **Connect** again. If your RD-6 shows up under a different name, set it under **Advanced → Connection**.

**The browser didn't ask for MIDI permission, or blocked it**
Use Chrome or Edge on a computer. Open the site settings (the icon at the left of the address bar), allow the page to control MIDI devices, reload the page and click **Connect** again.

**"Your RD-6 didn't switch to update mode"**
Press STOP so the RD-6 isn't playing, then try again. Nothing was written.

**An install or restore stopped part-way**

1. Don't unplug the RD-6 or switch it off.
2. Click **Save log file** under the message. The log records exactly what happened.
3. Click **Connect**. If the updater says the RD-6 is in update mode, choose **Restore → Official firmware 1.0.6** and try once.
4. If that fails too, stop and [open an issue](https://github.com/tracelistener/rd6-scatter/issues) with the log files attached. Don't keep retrying.

**"All of the firmware was written, but your RD-6 didn't answer"**
Click **Reconnect**. If the RD-6 then reports the version you installed, everything is fine.

**What the updater can't fix**
Install and restore both need the RD-6 to answer over USB. If it doesn't respond at all after an interrupted update, this updater can't recover it. That would need hardware debugging tools.

## Safety checks in the updater

- It accepts only firmware it recognises by checksum: official 1.0.5 and 1.0.6, and the Scatter builds. Anything else needs your typed confirmation, and a withdrawn test build is always refused.
- It checks the checksum and structure of every file it downloads or opens before using it.
- It doesn't switch the RD-6 to update mode until the RD-6 has answered with its version, and it confirms update mode with a read-only question before sending any firmware.
- It sends the firmware one block at a time and waits for the RD-6 to confirm each block. Any missing, extra or unexpected answer stops the transfer at once, and it never retries on its own.
- After the RD-6 restarts, it checks that the RD-6 reports the version that was just written.
