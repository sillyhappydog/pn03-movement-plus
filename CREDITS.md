# Credits

**P.N.03 Movement Plus** is made by [sillyhappydog](https://github.com/sillyhappydog).

P.N.03 is © 2003 Capcom Co., Ltd. GameCube is a trademark of Nintendo. This is an unofficial fan modification; it is not affiliated with or endorsed by Capcom or Nintendo.

No game data is distributed. The Dolphin patch files and the xdelta patches contain only this mod's own code and the few instruction words it replaces. The disc image, textures, models, music and everything else stay on your own copy of the game.

## Built on

- **The Resident Evil 4 (GameCube) decompilation** ([github.com/adonis-singh/re4](https://github.com/adonis-singh/re4), CC0). P.N.03 runs on the same Capcom engine, and that project is how the motion format (FCV), the effect system (ESP) and the texture containers of P.N.03 were understood: the quick-turn angles were read from the motion data, and the sprint trail colour was found through the effect system. My sincere thanks to its author. P.N.03 has no decompilation of its own; without that work these formats would have stayed a black box, and this mod would not exist in this form.
- **The symbol table Capcom left on the North American disc** (`MEKA.sym`), which names most of the game's functions and data.

## Tools

- **Dolphin**: emulator, debugger, the per-game patch system this mod is delivered through, and DolphinTool.
- **Capstone, Keystone and Unicorn**: disassembling the game, assembling the patch code, and running every build through emulated tests before it touched the game.
- **xdelta3**: the disc image patches.
- **Claude Code (Anthropic) and OpenAI Codex**: most of the analysis and the code were written with these, under my direction. The design, the in-game testing and every decision about what ships are mine.

## Images

The controller guide (`images/controller-guide.png`) was generated with ChatGPT's image generation from my layout and labels, then checked against the actual controls.

## Not included here

The HD texture pack is a separate release with its own credits.
