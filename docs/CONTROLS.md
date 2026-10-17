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

Roll and the extra Ratchet hits come only from the RD-6's audio outputs. They aren't sent over MIDI.

## Directions

- **Forward, Random and Ping-pong** start from the next step.
- **Reverse** waits for the start of the next bar, then plays the bar from step 16 back to step 1, rests included.
- Choosing Forward, Random or Ping-pong cancels a Reverse that hasn't started yet.
- The direction stays until you choose another one, turn Scatter off or press STOP.
- The running step light follows the step that's actually playing, including Slice jumps. (In the older Scatter v1, it showed the normal pattern position.)

## Pattern Write

If you switch to Pattern Write while a pattern plays, Scatter stays on and the direction keeps steering playback. In Write mode Scatter's controls are switched off, so the step buttons, TAP and PATTERN GROUP work as normal. Switch back to Pattern Play to use Scatter's controls again. STOP still turns Scatter off.

(The older Scatter v1 turned Scatter off and set the direction back to Forward when you switched to Pattern Write.)

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
