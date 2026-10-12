# LAN cooperative play

This checkout imports [pjasicek/OpenClaw](https://github.com/pjasicek/OpenClaw), pinned in `UPSTREAM_COMMIT`, and adds a native LAN cooperative implementation. Original level layouts, enemies, bosses, pickups, saves, and mission objectives are retained.

The Python server supports eight clients. It assigns unique red, blue, green, purple, gold, cyan, pink, and white coats. Blue fabric pixels in Claw's original sprites are recolored, with original shading and alpha retained. Red, blue, and green players have been visually checked together in Level 1; fur, trousers, and sword colors are preserved.

## Build

On Ubuntu/Debian, install the game dependencies, then compile:

```sh
sudo apt install build-essential cmake libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libsdl2-gfx-dev
cmake -S . -B build
cmake --build build -j 4
```

On Windows, build with the supplied Visual Studio solution or CMake. The LAN code links Winsock (`ws2_32`). Windows changes have not been compiled in this Linux environment. Build a fresh executable: the upstream prebuilt executables are single-player binaries.

Copy the full original game's `CLAW.REZ` to `Build_Release/CLAW.REZ` on every player's computer. Installations that use an empty REZ and loose files under `Assets` can be imported instead:

```sh
python3 Scripts/import_assets.py /path/to/CLAW-1.4.5.4
```

For this workspace, the files were imported from `/home/laptopprogramare/Downloads/CLAW-1.4.5.4`: 12,980 files were packed into a 102,382,990-byte archive. The importer preserves their bytes and leaves the original installation unchanged. All players must use the same archive and patched build. The original game assets are not distributed by this project. `Build_Release/ASSETS.ZIP` is included upstream; regenerate it from `Build_Release/ASSETS` if you change those files.

## Host and join

Run from the repository directory. Python 3.10 or newer is required; the server has no third-party dependencies.

Start the game menu:

```sh
python3 Scripts/play_lan.py
```

Choose **Multiplayer** (or press **M**) in the original main menu.

- **Host** (**H**) starts the local server and opens a lobby.
- **Join** (**J**) opens the host IP and port fields. Type the host's LAN IPv4 address, use **Tab** to switch fields, and press **Enter** to connect. Typing replaces the initially selected field; **Ctrl+A** selects it again.
- **Left/Right** chooses from eight coat colors. Colors already in use stay reserved to the other player; a message explains when a selection is unavailable.
- The lobby lists every connected player and their coat. The oldest connected player is the host; **Up/Down** selects mission 1–13 and **Enter** starts it for everyone. A late join automatically loads that same mission.
- **D** disconnects from the lobby and **Esc** returns to the previous menu. The built-in host server exits when its game exits or leaves the session. Use a dedicated server if the room should survive that computer leaving.

The native host needs Python 3.10+ available as `python3` on Linux/macOS or `python` on Windows, and the repository's `server` folder next to `Build_Release`.

The existing command-line shortcuts also work:

```sh
python3 Scripts/play_lan.py --host
python3 Scripts/play_lan.py --join 192.168.1.20
```

Use `python` instead of `python3` on Windows as appropriate. `--binary /path/to/executable` selects your compiled binary. The host's mission selection now loads the whole team together. The server supports upstream levels 1–13; it does not add unimplemented levels or change upstream progression restrictions. `--menu --port 27889` selects a different default port in the in-game menu.

**Restart the server and update every client to this build.** Protocol version 2 rejects older clients rather than silently mixing clients that cannot follow lobby mission changes.

For a dedicated server:

```sh
python3 server/lan_server.py --host 0.0.0.0 --port 27888
```

Allow inbound TCP port 27888 on the host's LAN firewall. Pass `--port` to both launcher and server to change it. The server is intended for a trusted LAN and does not authenticate players.

Alternatively, start the native client directly from `Build_Release`:

```sh
OPENCLAW_SERVER=192.168.1.20 OPENCLAW_PORT=27888 ./openclaw
```

Without `OPENCLAW_SERVER`, the original single-player mode runs. A connection failure or disconnect returns to local simulation; restart the client to reconnect. Restart the server, or disconnect all players, to start a fresh campaign session.

## Cooperative behavior

- Player positions, facing, and sprite frames are sent approximately 60 times per second. TCP packet batching is disabled, and remote movement is predicted over gaps of up to 34 ms with a short correction blend on every rendered frame. Teleports and respawns snap immediately. Offscreen avatars do not create coat textures or issue draw calls. Remote players have no damaging collision bodies, so friendly fire is disabled.
- The server owns health for actors loaded from the level. Accepted damage from any player reduces the same health total, and concurrent hits cannot overwrite one another. Scripted boss health reductions use the same path.
- Enemy positions, facing, and sprite frames are corrected from the oldest connected player in that mission at 5 Hz. That role transfers if they leave or change missions.
- The server accepts each shared pickup once. Its reward is applied to each player in that mission. Treasure, ammo, health, lives, and powerups therefore benefit the team. Loot dropped by registered actors receives stable identifiers derived from its parent and drop index.
- Checkpoints and mission completion are shared through the original game event handlers. Health, lives, inventory, and save files remain per player. Warps remain personal.
- Late joiners receive collected pickups, the last checkpoint, completion state, and registered actors' current health. Player coat slots are reused after disconnects; player IDs are never reused within a running server.

## Current limits and validation

This is an initial cooperative implementation, not a fully authoritative multiplayer rewrite. Enemy AI, projectile motion, moving platforms, boss scripts, and other world simulation still run on each client. Position correction can produce visible enemy jitter. Actors spawned by boss scripts outside the original level and registered loot path are not replicated. Different local combat or boss states can therefore diverge and need in-game verification before treating the campaign as reliably playable end to end. The host chooses missions and the next mission for everyone through the shared lobby or original game menus. Connected native clients are paced near 60 FPS to avoid unnecessary GPU/CPU competition when several clients run on one computer. Replaying an already completed mission requires a fresh server session.

Linux native compilation passes. Nine real TCP integration tests cover capacity, colors, shared damage, pickup deduplication, progress replay, mission isolation, enemy authority transfer, disconnects, and malformed packets. A C++ color test checks eight distinct ramps, preserved fur and neutral pixels, shading, and transparency:

```sh
python3 -m unittest discover -s tests -v
c++ -std=c++11 tests/coat_colors_test.cpp -o /tmp/openclaw-coat-test
/tmp/openclaw-coat-test
```

The supplied installation stores its original game data as loose files under `Assets`; its 168-byte REZ is intentionally empty. Those assets have now been imported successfully. Fourteen Python tests, the C++ color test, and remote motion tests pass.

The optional native smoke test starts two real clients in Level 1 on a private Xvfb display. It checks independent movement, shared crate damage and dropped loot, a third client joining after the loot was collected, and checkpoint/completion events through the original game handlers. Checkpoint and completion messages are injected by the test server; it does not walk to the end of the level. It captures the two coat colors in `artifacts/lan-smoke/cooperative-coats.png`. Linux requires `Xvfb`, `xdotool`, and ImageMagick's `import` command:

```sh
python3 tests/native_lan_smoke.py
```

The native lobby test starts three clients from the original main menu, creates a server through Host, connects two clients through Join, selects red/blue/green coats, starts the same mission on all three, and verifies that each client renders both others while they move and jump:

```sh
python3 tests/native_lobby_smoke.py
c++ -std=c++11 tests/remote_motion_test.cpp -o /tmp/openclaw-motion-test
/tmp/openclaw-motion-test
```

Screenshots are saved under `artifacts/lobby-smoke`. Full campaign and boss encounters still require playtesting. MIDI music also requires the upstream timidity configuration; the development environment currently lacks `timidity.cfg`.
