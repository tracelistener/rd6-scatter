# Scatter controls

Scatter works in **PATTERN PLAY** mode while a pattern is playing. You choose one effect and, separately, one playback direction.

## Turn Scatter on and off

- **Turn on:** hold FUNCTION and press TAP, then let go of both.
- **Play the effect:** hold TAP. When you let go, the pattern carries on in the selected direction (unless Latch is on).
- **Turn off:** hold FUNCTION and press TAP again, or press STOP. Both set the direction back to Forward. STOP also turns the effect off.

## Step buttons while Scatter is on

| Button | What it does |
|---|---|
| **1** | Roll (straight) |
| **2** | Ratchet |
| **3** | Slice |
| **4** | Cut |
| **5 – 8** | Depth 1 – 4 (see [Effects and depth](#effects-and-depth)) |
| **9** | Forward |
| **10** | Reverse |
| **11** | Random |
| **12** | Ping-pong |
| **13** | Roll timing: straight |
| **14** | Roll timing: triplet |
| **15** or **PATTERN GROUP** | Latch on/off: the effect keeps playing after you let go of TAP |
| **16** | Effect off. Also turns Latch off. If you're holding TAP, it does nothing until you let go and press it again |
| **TAP** | Hold to play the selected effect |
| **START/STOP** | Start and stop as usual. STOP also turns Scatter off, turns the effect off and sets Forward |

## Effects and depth

- **Roll** repeats the last hit or chord. Depth sets the speed: depth 1 = 1/8 notes, depth 2 = 1/16, depths 3 and 4 = 1/32. Buttons 13 and 14 choose straight or triplet timing.
- **Ratchet** plays each programmed hit as fast repeats: 2 per hit at depths 1 and 2, 4 per hit at depths 3 and 4.
- **Slice** jumps around, repeats and reverses parts of the pattern. Each depth is a different rhythmic variation.
- **Cut** mutes hits in rhythmic patterns. Sounds that are already ringing still decay naturally. Each depth is a different rhythmic variation.

Roll and the extra Ratchet hits come only from the RD-6's audio outputs. They aren't sent over MIDI, except in the [MIDI extra-hit test build](#midi-extra-hit-test-build).

## Directions

- **Forward, Random and Ping-pong** start from the next step.
- **Reverse** waits for the start of the next bar, then plays the bar from step 16 back to step 1, rests included.
- Choosing Forward, Random or Ping-pong cancels a Reverse that hasn't started yet.
- The direction stays until you choose another one, turn Scatter off or press STOP.
- The running step light follows the step that's actually playing, including Slice jumps. (In the older Scatter v1, it showed the normal pattern position.)

## Pattern Write

If you switch to Pattern Write while a pattern plays, Scatter stays on and the direction keeps steering playback. In Write mode Scatter's controls are switched off, so the step buttons, TAP and PATTERN GROUP work as normal. Switch back to Pattern Play to use Scatter's controls again. STOP still turns Scatter off.

(The older Scatter v1 turned Scatter off and set the direction back to Forward when you switched to Pattern Write.)

## Mute and roll mode

Mute and roll mode is a performance mode modelled on the Quicksilver 606's mute and roll mode. It works in **PATTERN PLAY** while a pattern is playing.

- **Enter or leave:** double-click **FUNCTION**. Press nothing else during either click.
- **Step lights:** steps 1–8 lit = that voice is playing; steps 9–16 lit = its roll is on.

| Button | What it does |
|---|---|
| **1 – 8** | Mute or unmute BD, SD, LT, HT, CY, CP, OH, CH. You can press several at once |
| **9 – 16** | Roll on or off for the same voices, in the same order |
| **PATTERN GROUP** | Mute or unmute the accent |
| **Hold TAP + 9 – 14** | Roll rate: off, 1/32, 1/16, 1/8, 1/4, 1/2. While you hold TAP, the lit step shows the rate |
| **Hold TAP + 15** | All rolls off |
| **Hold TAP + 16** | Unmute everything |

The roll rate starts at **off**, so pick one before rolls play: for example, hold TAP and press 11 for 1/16. Rolls play the voice on top of the pattern: 1/16 on every step, 1/8 on every second step, 1/4 on every fourth and 1/2 on every eighth. 1/32 plays twice per step, except the clap, which plays once.

### Length per voice

Each voice can loop over its own number of steps, so it drifts against the rest of the pattern.

1. In mute and roll mode, **hold** the voice's button (1–8). After about half a second the step lights show its length, and the voice keeps its mute setting.
2. Keep holding it and press the step for the new length: step 5 = 5 steps.
3. To make the voice follow the pattern again, hold its button and press **TAP**.

A voice with its own length starts from its first step when you press Start and always plays forward, whatever Scatter's direction. It's silent on steps that Scatter's effects cut out.

### Good to know

- Stopping, or leaving Pattern Play, ends the mode. Mutes, rolls, the rate and the lengths stay, and keep working in every mode, until you switch the RD-6 off.
- In the mode, steps, TAP and PATTERN GROUP only do what's listed above: Scatter's own buttons and the RD-6's pattern selection wait until you leave. START/STOP works as usual.
- MIDI out sends what plays, including mutes, rolls and lengths. The second hit of a 1/32 roll is the exception: it isn't sent over MIDI, except in the [MIDI extra-hit test build](#midi-extra-hit-test-build).

## Shortcuts without turning Scatter on

Hold **FUNCTION first**, then press a step button:

| Step | Effect |
|---|---|
| **1** | Roll |
| **2** | Ratchet |
| **3** | Slice |
| **4** | Cut |
| **5 / 6** | Roll 1/8, straight / triplet |
| **7 / 8** | Roll 1/16, straight / triplet |
| **9 / 10** | Roll 1/32, straight / triplet |

The effect plays while you keep holding FUNCTION and stops when you let go. Without FUNCTION, the step buttons work as normal.

## Settings

Scatter doesn't save its settings. After you switch the RD-6 on, Scatter is off, Latch is off and the direction is Forward.

## MIDI control

Send **CC 110** on the RD-6's MIDI receive channel to choose an effect from a sequencer or controller:

| CC 110 value | Effect |
|---|---|
| 0 – 3 | Off |
| 4 – 7 | Slice, depth 1 – 4 |
| 8 – 11 | Cut, depth 1 – 4 |
| 12 – 15 | Ignored |
| 16 – 19 | Ratchet, depth 1 – 4 |
| 20 – 23 | Roll (straight), depth 1 – 4 |
| 24 – 27 | Roll (triplet), depth 1 – 4 |

Within each group of four values, the first value is depth 1 and the last is depth 4. For example, 4 is Slice at depth 1 and 7 is Slice at depth 4.

**CC 112** with value 0 asks Scatter for a status report. It's a diagnostic for development; see the [technical notes](TECHNICAL.md#scatter-status-report).

## MIDI extra-hit test build

The updater has an unticked option, **MIDI extra-hit test build**. It's Scatter v1.3 with one change: the extra hits that normally come only from the audio outputs are also sent on MIDI out, the same way the RD-6 sends its regular hits. That covers Roll (straight and triplet, also when it's latched), the extra Ratchet hits, and the second hit of a 1/32 roll in mute and roll mode. The buttons and the timing are the same as in v1.3. **This build hasn't been tested on hardware yet.**

- The notes go out on the RD-6's MIDI transmit channel, over USB and the MIDI OUT socket: BD 36, SD 40, LT 45, HT 50, CY 51, CP 39, OH 46, CH 42. Velocity is 80, or 112 with accent. Each note gets its note-off shortly after, like the RD-6's regular notes.
- Muted voices send nothing, and a voice with its own length sends what it plays.
- The RD-6's own clap skips a repeat that would need its accent set-up (an accented repeat, or one just after an accented clap), but MIDI out still sends it. Scatter's other clap protection is unchanged.
- When MIDI out is very busy, an extra note is left out rather than sent late. The audio outputs still play it. Dense chords at fast repeat rates can need more than MIDI can carry.
- To go back to normal Scatter v1.3, install again without ticking the option.

### Testing it

1. Connect a MIDI monitor to the RD-6's MIDI OUT. Start with a slow, sparse pattern and one voice at a time, and check normal playback first.
2. Play Ratchet at depths 1–2 (two hits) and 3–4 (four hits), straight and triplet Roll at every depth, and Roll with Latch on after you let go of TAP, each with and without accent. In mute and roll mode, try a 1/32 roll (hold TAP and press 10), with and without a muted voice.
3. Check that every repeat sends a note-on with the note and velocity above, followed by its note-off. Let go of the effect, turn Latch off and press STOP: the repeats should stop, every note should get its note-off, and normal playback should carry on with no missing or stuck notes. Then try chords and faster tempos. If you use USB MIDI, check it separately.
4. Connect the Rhythm Wolf or RD-9 instead of the monitor, and set its receive channel and note numbers to match the RD-6. Repeat the tests and listen for the added hits, steady clock, start and stop, and any unexpected flams, gaps, missing hits or hanging notes.
5. Save the monitor log, and note the tempo, voices, depth, straight or triplet, accent, latch and the receiving device.
