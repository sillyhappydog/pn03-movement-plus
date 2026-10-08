# Installation

Two ways to play the mod. Pick one.

| | Dolphin patch files (recommended) | Patched disc image (xdelta) |
|---|---|---|
| Where it works | Dolphin only | Dolphin, other emulators, real hardware (hardware untested) |
| What you need | the game as an ISO/GCM/RVZ in Dolphin, plus one text file per region from `dolphin/` | an unmodified ISO of the game, `xdelta3`, plus the `.xdelta` file from `xdelta/` |
| Turn single features on and off | yes (checkboxes in Dolphin) | no (all nine changes are baked in) |
| Game files modified | none | a new ISO is written; the original is untouched |

Both regions are supported: the Japanese release **GPNJ08** and the North American release **GPNE08**. The European release (GPNP08) is not supported.

The HD texture pack is a separate download and works with either method, see the end of this page.

## A. Dolphin patch files

The mod is delivered as Dolphin "patches": a list of memory words Dolphin writes while the game runs. They live in the per-game settings file, so nothing on the disc image changes.

1. Find Dolphin's `GameSettings` folder.
   - Windows: `C:\Users\<you>\Documents\Dolphin Emulator\GameSettings\`
   - If your Dolphin runs in portable mode (a `portable.txt` next to `Dolphin.exe`), it is `User\GameSettings\` inside the Dolphin folder instead.
   - Linux: `~/.local/share/dolphin-emu/GameSettings/`, macOS: `~/Library/Application Support/Dolphin/GameSettings/` (not tested here).
2. Copy the file for your region from this package's `dolphin/` folder into that folder:
   - Japanese disc: `dolphin/GPNJ08.ini`
   - North American disc: `dolphin/GPNE08.ini`
   - If a file with that name already exists (you made per-game settings before), open both in a text editor and paste the `[OnFrame]` and `[OnFrame_Enabled]` sections from ours to the end of yours.
3. Start the game. Nothing else to configure.

To check that it took: hold L and R and press Z during play. A tuning menu appears at the bottom left (`DEBUG CAM SENS ...`). Press L + R + Z again to close it. If nothing appears, Dolphin did not load the file: check the folder, the file name (it must match the game ID shown in Dolphin's game list) and that the file is plain text.

### Turning features on and off

Right-click the game in Dolphin's list, choose **Properties**, open the **Patches** tab. Each of the nine changes is a checkbox:

| Patch | What it does | Depends on |
|---|---|---|
| C-Stick Independent Camera v0.11 | Free camera on the C-stick, camera reset on X | needs Camera Relative Movement |
| Camera Relative Movement v0.20 | Camera-relative running, jumps, side-steps, crouch, quick turns, tuning menu | needs C-Stick Independent Camera |
| Dodge Absorb v0.2 | Invincible side-steps that absorb shots (+100 Energy per shot) | — |
| Sprint Run v0.3 | Sprint after about 1.5 s of running | — |
| Sprint Trail Color v0.3 | Orange hand/foot trails while sprinting | needs Sprint Run |
| Energy Drive Terrain Pass v0.1 | Energy Drive shots pass through terrain | — |
| Shot Speed v0.1 | Normal shots 2.5× faster | — |
| Lead Aim v0.1 | Normal shots lead a locked target | — |
| Transition Null Projection v0.1 | Removes the stray triangles between the Mission 9 fights (Dolphin only) | — |

Keep the camera and movement patches together: one without the other falls back to the original controls in a confusing way. The rest can be mixed freely.

### Requirements and caveats

- Tested with Dolphin 2609. The patch lines use Dolphin's four-field conditional format (`address:dword:value:original`); builds older than 2023 do not understand it. Use a current release or development build.
- **Do not load savestates made without the mod, or with an older version of it.** A savestate restores the whole memory, including old patch code. Continue from a memory-card save after installing or updating. Saves themselves are unaffected and keep working.
- Updating: the new `GPNJ08.ini` / `GPNE08.ini` replaces the old one. If you merged by hand, delete the old `[OnFrame]` entries (their names carry version numbers) before pasting the new ones.
- Uninstalling: delete the file, or untick the patches.

## B. Patched disc image (xdelta)

The `xdelta/` folder holds a binary patch per region that turns the original disc image into the modded one. The nine changes are baked into the game's executable; the rest of the disc is byte-identical.

1. You need an unmodified dump of your disc as a plain ISO (1,459,978,240 bytes for both regions). SHA-256 of the originals:
   - GPNJ08: `7ed9a911f6dd63664f8e4fea8fa8e61ca00d23f57cf989d12d1b42780ba79b7d`
   - GPNE08: `f1dd381e06af72dc2bb51d94b05cc453c36e70bf23d63f4f01f7ba579534a0f2`
   - Compressed formats (RVZ, GCZ) must be converted back to ISO first (Dolphin: right-click → Convert File).
2. Apply the patch with `xdelta3` (command line) or any xdelta3-compatible GUI patcher:
   ```
   xdelta3 -d -s original.iso GPNJ08-pn04-v0.1.xdelta GPNJ08-pn04-v0.1.iso
   ```
   (use the `GPNE08` files for the North American disc.) The patch refuses a source that does not match.
3. Expected result, SHA-256:
   - GPNJ08: `75d66c26109f56951548ae0263fb90493e0d10e9fae3dea000b63bcbcb06e01c`
   - GPNE08: `f500b76e8837881435a3c13856f457217f10f0f11017a31f64b1bd722a379228`
4. Play the new ISO. The game ID is unchanged, so existing memory-card saves are found as usual.

If you also installed the Dolphin patch files for the same game ID, Dolphin applies them on top of the patched ISO. They are harmless (their hooks only write where the original code is still present), but to keep things simple untick them while playing the patched ISO.

What the xdelta changes: the main executable (`main.dol`) gets the nine patches written in place plus a new code section at its end, and the file table of the disc moves to make room. No game file is altered. Both images boot and play in Dolphin; real hardware has not been tried yet.

## HD texture pack (optional, separate download)

Download: [https://archive.org/details/pn03-hd-texture-pack](https://archive.org/details/pn03-hd-texture-pack) (`PN03-HD-Texture-Pack-GPN-v1.0.zip`, 1.41 GiB; the SHA-256 is in `SHA256SUMS.txt` next to it).

Upscaled textures for both regions. In Dolphin, put the pack's `GPN` folder under `Load\Textures\` (next to `GameSettings`, so `...\Dolphin Emulator\Load\Textures\GPN\`) and enable **Load Custom Textures** in Graphics → Advanced. The three-letter folder name serves both GPNJ08 and GPNE08; if you keep your own `GPNJ08` or `GPNE08` texture folder there, Dolphin uses that one instead. The pack works the same with the patch files and with the patched ISO.
