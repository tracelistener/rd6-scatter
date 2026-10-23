# RD-6 Scatter

Scatter is unofficial custom firmware for the **Behringer RD-6** drum machine. It adds four live effects that you play with the TAP button while a pattern runs:

| Effect | What it does |
|---|---|
| **Roll** | Repeats the last hit or chord |
| **Ratchet** | Plays each programmed hit as 2 or 4 fast repeats |
| **Slice** | Jumps around, repeats and reverses parts of the pattern |
| **Cut** | Mutes hits in rhythmic patterns |

You can also play patterns **Forward, Reverse, Random or Ping-pong**.

> [!WARNING]
> Scatter is experimental and is not made or supported by Behringer. So far it has been tested on one RD-6. You can go back to the official firmware at any time with the same updater.

### [Open the updater →](https://tracelistener.github.io/rd6-scatter/)

The updater runs in your web browser. There's nothing to download or install.

## What you need

- A Behringer RD-6 and a USB cable
- A computer with **Google Chrome** or **Microsoft Edge** (other browsers can't send firmware to MIDI devices)

Close SynthTribe and any other music software before you start.

## Install Scatter

1. Open the [updater](https://tracelistener.github.io/rd6-scatter/). Connect the RD-6 by USB, switch it on and press **STOP**.
2. Click **Connect**. If the browser asks whether the page may control your MIDI devices, choose **Allow**.
3. Under **Back up**, click **Save backup**, keep the file somewhere safe and tick the box to confirm you saved it. If the updater says there's nothing to back up, skip this. See [About backups](#about-backups).
4. Also click **Save patterns and settings**. It's optional, but it keeps a copy of all your patterns.
5. Choose **Install Scatter**, tick the box to confirm you understand Scatter is experimental, then click **Install Scatter**.
6. Wait until the updater says **Done**. It usually takes under a minute. While it works, keep the tab open and in front, and don't unplug the RD-6. If the updater says Chrome lost its connection to the RD-6, click **Reconnect** and carry on.

## About Scatter v1.4.1

Scatter v1.4.1 is built on Behringer's firmware **1.0.5** and includes the bug fix from Behringer's newest firmware, **1.0.6**: the RD-6 keeps the pattern number you picked when you change pattern group during playback ([Behringer's release notes](https://mediadl.musictribe.com/download/software/behringer/RD6/Release-Notes_BE_RD-6_v1-0-6_Rev.1.pdf)).

After you install it, your RD-6 reports firmware **1.0.5**. That's expected.

New in v1.4.1:

- **Easier voice lengths.** After a voice's length shows, you can let go of its button: the length stays on show for about two seconds, so you can press any step, the voice's own button included, and see the new length ([details](docs/CONTROLS.md#length-per-voice)).

From v1.4:

- **Repeats on MIDI out.** Roll, the extra Ratchet hits and the second hit of a 1/32 roll are sent on MIDI out too, so a drum machine played from the RD-6's MIDI out repeats along ([details](docs/CONTROLS.md#midi-out)).
- **Each pattern keeps its voice lengths.** A loop length you give a voice in mute and roll mode is saved with the pattern, so it's still there after you switch the RD-6 off ([details](docs/CONTROLS.md#length-per-voice)).
- **Pattern Write shows a voice's own loop.** Select a voice with its own length and the running light goes round that voice's loop, with its unused steps dark.

From v1.3:

- **Mute and roll mode.** While a pattern plays, double-click FUNCTION. Steps 1–8 mute the voices, steps 9–16 add rolls, and you can give each voice its own loop length ([how it works](docs/CONTROLS.md#mute-and-roll-mode)).

From v1.2:

- **The step lights follow the playback direction.** In Reverse, Random or Ping-pong, the running light shows the step that's actually playing.
- **Scatter stays on in Pattern Write.** The direction you chose keeps playing while you edit, and the buttons do their normal Write jobs. Scatter's controls work again when you go back to Pattern Play.

Already have an older Scatter? Install again the same way to get v1.4.1.

## Go back to the official firmware

1. Open the [updater](https://tracelistener.github.io/rd6-scatter/) and click **Connect**.
2. Choose **Restore**, then choose one of these:
   - **Official firmware 1.0.6**: Behringer's newest version. No file needed.
   - **Firmware from a file**: the firmware backup you saved before you installed Scatter.
3. Click the restore button and wait until the updater says **Done**.

To put your patterns back, choose **Restore → Patterns and settings from a file** and pick your patterns file. That doesn't change the firmware.

## About backups

The updater saves two kinds of backup.

**Firmware.** The RD-6 has no way to send its firmware back to a computer, so the updater can't copy it. Instead, it asks your RD-6 which version it runs and saves Behringer's official file for that version. Restoring that file puts the same official firmware back.

- **Official 1.0.6 or 1.0.5:** the backup is that version.
- **Scatter already installed:** there's nothing to back up. You can reinstall Scatter or restore official 1.0.6 whenever you like. Scatter also reports version 1.0.5, so if your RD-6 reports 1.0.5 the updater asks which one you have.
- **Any other version:** the updater tells you it can't make a backup. You can still restore official 1.0.6 later, or install Behringer's newest firmware with their SynthTribe app.

**Patterns and settings.** These are read straight from your RD-6: all 32 patterns (2 groups of 16) and its settings, such as the MIDI channels. They're saved in one file you can restore later. They're kept separately from the firmware, so installing Scatter or restoring firmware doesn't change them.

More detail and troubleshooting: [Backup, restore and troubleshooting](docs/BACKUP_RESTORE.md).

## Playing Scatter

Start a pattern in PATTERN PLAY mode, then:

1. Hold **FUNCTION** and press **TAP** to turn Scatter on. Let go of both.
2. Use the step buttons to choose an effect, a depth and a direction.
3. Hold **TAP** to play the effect. Let go to hear the normal pattern again.

| | | | |
|---|---|---|---|
| **1** Roll | **2** Ratchet | **3** Slice | **4** Cut |
| **5** Depth 1 | **6** Depth 2 | **7** Depth 3 | **8** Depth 4 |
| **9** Forward | **10** Reverse | **11** Random | **12** Ping-pong |
| **13** Straight roll | **14** Triplet roll | **15** Latch | **16** Effect off |

- **Latch** (step 15, or PATTERN GROUP) keeps the effect playing after you let go of TAP. **Effect off** (step 16) stops it.
- A **direction** stays on until you choose another one or leave Scatter, and the step lights follow it. Reverse starts at the next bar.
- Switching to **Pattern Write** keeps Scatter on, but its buttons rest until you go back to Pattern Play.
- To **leave Scatter**, hold FUNCTION and press TAP again, or press STOP. Either way the direction goes back to Forward, and STOP also turns the effect off.
- **Mute and roll mode:** double-click FUNCTION while a pattern plays. Steps 1–8 mute or unmute the voices and steps 9–16 switch their rolls on or off. Hold TAP and press step 9–14 to pick the roll rate. Hold a voice's mute button until its length shows, then press a step (you can let go first) to give that voice its own loop length. Double-click FUNCTION again to leave.
- Roll and the extra Ratchet hits play on MIDI out as well as the audio outputs.
- Scatter saves each pattern's voice lengths. Its other settings reset when you switch the RD-6 off.

Shortcuts, depth details and MIDI control: [Scatter controls](docs/CONTROLS.md).

## Known limitations

- Scatter has been tested on one RD-6 only.
- It hasn't been tested with an external MIDI clock or with other devices chained to the RD-6.
- Ratchet can glitch at very fast tempos. This is known and not fixed yet.
- The voice lengths aren't part of the updater's patterns and settings backup.
- The updater can only help while the RD-6 still responds over USB. If an update is interrupted, see [If something goes wrong](docs/BACKUP_RESTORE.md#if-something-goes-wrong).

## For developers

How Scatter is built, how the updater works and how to run the checks: [Technical notes](docs/TECHNICAL.md).

## Legal

Scatter is an independent project. It isn't affiliated with Behringer, Music Tribe or Roland. The files in `firmware/` are unmodified copies of Behringer's official updates and belong to their owner.
