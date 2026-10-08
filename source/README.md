# Source packages

One folder per patch, as built. Each holds the patch file for both regions (`GPNJ08-*.patch.txt`, `GPNE08-*.patch.txt`), the build script, the assembled body (`*.s`, `*.bin`), the tests and the manifest: the Japanese build in `source/`, the North American build in `source-us/`. The `README.md` in each package is the development note for that patch, in Japanese.

| Package | Patch |
|---|---|
| `pn03-cstick-camera-v11/` | C-Stick Independent Camera v0.11 |
| `pn03-camera-move-v20/` | Camera Relative Movement v0.20 |
| `pn03-dodge-absorb-v02/` | Dodge Absorb v0.2 |
| `pn03-sprint-run-v03/` | Sprint Run v0.3 |
| `pn03-sprint-trail-v03/` | Sprint Trail Color v0.3 |
| `pn03-ed-terrain-v01/` | Energy Drive Terrain Pass v0.1 |
| `pn03-shot-speed-v01/` | Shot Speed v0.1 |
| `pn03-lead-aim-v01/` | Lead Aim v0.1 |
| `pn03-transition-nullproj-v01/` | Transition Null Projection v0.1 |

Rebuilding a patch needs Python 3 with `capstone`, `keystone-engine` and `unicorn` (`pip install capstone keystone-engine unicorn`) and your own `main.dol` extracted from the disc. The scripts read the DOL from the path set in `dol.py` (`PATH`) or `regions.py` (`dol_path`); point that at your file first. The tests run under Unicorn and do not need the game.
