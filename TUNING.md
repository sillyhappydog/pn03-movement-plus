# Tuning

Two values can be changed while playing: the camera sensitivity and the jump timing window. Everything else is fixed in the patch files, with a short list of the numbers worth changing for people who want to edit the files.

## The tuning menu

Hold **L + R** and press **Z** during play. Vanessa stops (the camera still turns) and three lines appear at the bottom left:

```
DEBUG CAM SENS 0.0036  X6.00
DPAD=SENS X=RESET L+R+Z=EXIT
JUMP WIN 04 A/B
```

| Input | Effect |
|---|---|
| D-pad up / down | Camera sensitivity ±1.00 on the multiplier (±0.0006 on the raw value) |
| D-pad left / right | Fine step, ±0.0001 |
| A / B | Jump window +1 / −1 frame (0 to 30) |
| X | Both values back to their defaults |
| L + R + Z | Close the menu |

Values live in memory only: they go back to the defaults when the game is restarted. To make a value permanent, edit the patch file (next section).

**Camera sensitivity** is how far the camera turns per frame for a full C-stick push: the raw value is radians per stick unit per frame, the `X` figure is that value relative to the original mod's 0.0006. The default `0.0036` (`X6.00`) turns about 24 degrees per frame at full deflection. The range is 0.0002 to 0.05.

**Jump window** is how many frames after a stick push a press of B still counts as "stick + B together", which makes the jump screen-relative (down + B is a back jump toward the camera, up + B a forward jump away, left/right + B a vertical jump drifting sideways). Pressing B later than the window gives a forward jump in the running direction. Default 4 frames. 0 switches the chord detection off (every B is a forward jump); larger values make the back jump easier to get at the cost of a slight delay before a backward push starts Vanessa running.

## Changing defaults in the patch files

Each patch file is a list of lines `address:dword:value:original`. A few lines are plain parameters: change the `value` word, keep everything else. The files are `dolphin/GPNJ08.ini` and `dolphin/GPNE08.ini`; the addresses differ between regions (the US ones are the JP ones + 0x3C00), the values are the same. Floats are IEEE single precision written as 8 hex digits (0.0036 = `3B6BEDFA`, 1.0 = `3F800000`, 1.4 = `3FB33333`, 2.5 = `40200000`); a converter such as `float.exposed` or Python's `struct.pack('>f', x).hex()` gives the word.

| What | Default | GPNJ08 line | GPNE08 line |
|---|---|---|---|
| Camera sensitivity default (the value the tuning menu starts from) | 0.0036 (6.00×) | `0x8018E0E4:dword:0x3B6BEDFA:0x00000000` | `0x80191CE4:dword:0x3B6BEDFA:0x00000000` |
| Camera sensitivity fallback used by the camera alone (keep equal to the one above) | 0.0036 | `0x801910E8:dword:0x3B6BEDFA:0x00000000` | `0x80194CE8:dword:0x3B6BEDFA:0x00000000` |
| Jump window default (frames) | 4 | `0x8018E12C:dword:0x00000004:0x00000000` | `0x80191D2C:dword:0x00000004:0x00000000` |
| Jump window maximum the menu allows | 30 | `0x8018E130:dword:0x0000001E:0x00000000` | `0x80191D30:dword:0x0000001E:0x00000000` |
| Camera reset (X) swing speed, radians per frame | 30° = `3F060A92` | `0x80191110:dword:0x3F060A92:0x00000000` | `0x80194D10:dword:0x3F060A92:0x00000000` |
| Energy absorbed per shot during a side-step | 100 (`li` immediate: keep the top byte `38 00`, the low 16 bits are the amount) | `0x8018C824:dword:0x38000064:0x00000000` | `0x80190424:dword:0x38000064:0x00000000` |
| Sprint: frames of running before the sprint starts | 45 (1.5 s; `li` immediate, low 16 bits) | `0x8018D824:dword:0x3800002D:0x00000000` | `0x80191424:dword:0x3800002D:0x00000000` |
| Sprint: frames to ramp up to full speed | 15 (`li` immediate, low 16 bits) | `0x8018D82C:dword:0x3800000F:0x00000000` | `0x8019142C:dword:0x3800000F:0x00000000` |
| Sprint: top speed factor (float, 2.0 at most) | 1.4 | `0x8018DD1C:dword:0x3FB33333:0x00000000` | `0x8019191C:dword:0x3FB33333:0x00000000` |
| Sprint: turn that cancels the sprint (radians per frame, float) | 60° = `3F860A92` | `0x8018DD20:dword:0x3F860A92:0x00000000` | `0x80191920:dword:0x3F860A92:0x00000000` |
| Sprint trail colour, two lines: the low 16 bits of the first are `RRGG`, the low 16 bits of the second are `BB00` | orange `FF8800` | `0x8018D424:dword:0x3C00FF88:0x00000000` and `0x8018D428:dword:0x60000000:0x00000000` | `0x80191024:dword:0x3C00FF88:0x00000000` and `0x80191028:dword:0x60000000:0x00000000` |
| Normal shot speed factor (float) | 2.5 | `0x8018C708:dword:0x40200000:0x00000000` | `0x80190308:dword:0x40200000:0x00000000` |
| Lead aim strength (float, 0 = aim at the current position, 1 = full lead) | 1.0 | `0x8018C508:dword:0x3F800000:0x00000000` | `0x80190108:dword:0x3F800000:0x00000000` |

Not worth changing: the rotation the camera assumes for the C-stick quarter turn (80.64°, measured from the game's own animation), the thresholds of the side-step and crouch direction rules, and the camera's direction rule for near-opposite targets. They are documented in the source packages.

After editing, restart the game (and do not load a savestate made with the old values). The patched-ISO builds carry the defaults listed above; changing them there means rebuilding the ISO from the sources.
