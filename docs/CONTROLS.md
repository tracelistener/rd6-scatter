# TEST12 controls

Use PATTERN PLAY while running. FUNCTION+TAP enters/exits the layer; release both before a fresh TAP trigger. One effect plus one independent direction.

| Buttons | Action |
|---|---|
| 1 / 2 / 3 / 4 | Roll (straight) / Ratchet / Slice / Cut |
| 5 / 6 / 7 / 8 | Depth/rate1 /2 /3 /4 |
| 9 /10 /11 /12 | Forward / Reverse / Random / Ping-pong |
| 13 /14 | Select straight/triplet Roll |
| 15 or PATTERN GROUP | Toggle latch |
| 16 | Effect off; cancel latch and inhibit held TAP until release |
| TAP | Momentary trigger; release restores selected direction unless latched |
| START/STOP | Stock transport; Stop also exits the layer, effect off, Forward |

Roll rates by depth:1/8,1/16,1/32,1/32. Ratchet uses two subdivisions at depths1/2, four at depths3/4. Slice/Cut each have four rhythmic scripts. Reverse waits for the next bar before16→1. Other direction choices apply next regular step and cancel pending Reverse. LEDs show stock clock, not transformed source steps. No Scatter settings are saved to EEPROM.

Outside the layer, hold FUNCTION first, then Step1 Roll, Step2 Ratchet, Step3 Slice or Step4 Cut. Keep FUNCTION held; release ends the effect. Six dedicated Roll shortcuts remain: Steps5/6=1/8 straight/triplet,7/8=1/16,9/10=1/32. Ordinary step buttons outside the layer retain stock behavior.

CC110 on the configured receive channel:0..3 off,4..7 Slice,8..11 Cut,16..19 Ratchet,20..23 straight Roll,24..27 triplet Roll.12..15 rejected. Values within each four-value group select depths1..4. CC112/value0 requests the13-field build12 diagnostic reply.
