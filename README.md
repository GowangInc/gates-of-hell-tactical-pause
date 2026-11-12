# Gates of Hell: tactical pause

Experimental tactical pause for **solo Dynamic Conquest** in *Call to Arms – Gates of Hell: Ostfront*: freeze the battle, select different units, give native orders, then resume. This is a real pause, not slow motion. Ordinary single-player campaign active pause is left intact.

**Version 0.3.2 · tested with game 1.067.0, Steam build 25492057, on one Linux/Proton system.** This is an expert/manual installation, not a general-purpose installer. No multiplayer or co-op support; no Windows or Steam Deck compatibility claim.

## What was tested

- Selecting an officer and a separate squad while frozen, assigning different destinations, and observing both execute their orders on resume.
- Camera movement/zoom, order replacement, cancellation and native Shift-waypoint execution.
- Pausing with an MP40 trigger held: ammunition consumption stopped and resumed with the simulation.
- Single-player `Cold Supper`: native paused selection/orders and subsequent execution.
- Conquest retreat while paused: cancelling preserves pause; confirming resumes the native server so saving and mission completion finish. The saved operation reloaded successfully.
- Cold GOHSE loading, managed-patch rollback and normal game/launcher shutdown.

These checks are not coverage of every action, weapon, mission or mod combination. Manual save/load **inside** an actively paused mission is not established. Back up your saves and use an isolated copy.

## Read before running

This uses **GOHSE, an external native-code loader, and native memory patches**. Lua is not a sandbox: review this source and the loader, and do not treat the separate Proton prefix as protection from malicious code. No game executable or dependency DLL is distributed here.

Use only offline single-player campaign or solo Conquest. Do not use it in multiplayer, co-op or a protected session, and do not disable anti-cheat, DRM or server checks to make it run. The supported launcher enforces its offline/network checks; the Lua environment flag alone is **not** a security boundary. Do not set that flag manually or add it to ordinary Steam launch options.

This is distributed outside Steam Workshop. Read the developers' [Workshop policy announcement](https://store.steampowered.com/news/app/400750/view/715668461242548712), particularly before redistributing native-loader-based mods.

## Requirements and current portability limits

- An owned installation of game **1.067.0** with client SHA-256:
  `4b6a807ad867c4f6eb1019376224d74fa3a6ac048355739ab0b76d73c7c0a267`.
- **[GOHSE 0.1.1](https://github.com/nature2468/gohse/releases/tag/v0.1.1)**. The tested `version.dll` SHA-256 is:
  `8664a225b0615992834f7408d58ff1ae5df1c9e9eff8811d8e7c0f44f4d1c426`.
  Obtain it from the loader's own release, not an unsolicited DLL mirror. Read its installation notes and dependency notices.
- Linux/X11, Python **3.9+** with Tk, and installed `socat`, `unshare`, `mount`, `bash`, `ip` and `xdotool`. Working rootless user/network/mount namespaces, pidfds and access to the owned game's `/proc/<pid>/mem` are required. Distribution security settings may refuse this; do not weaken system security settings as a workaround.
- The launcher currently assumes Steam at `~/.steam/debian-installation`, with the game, **Proton Experimental** and **SteamLinuxRuntime_sniper** in that Steam library.
- It bridges only the existing host-loopback Steam IPC ports **57343, 18183 and 27667** into a private network namespace. These were measured on the tested system, not established as portable Steam defaults. A different Steam layout/IPC arrangement needs separate investigation; do not forward gameplay traffic or substitute remote endpoints.
- An already prepared, real, separate Proton prefix, defaulting to `~/.local/share/goh-tactical-pause/compatdata`, **outside the installed mod folder**. Use `--prefix /absolute/path/to/private-compatdata` to select an existing copy. The launcher does **not** install GOHSE, create this prefix, or migrate saves automatically.

Unsupported executable hashes fail closed. Do not remove the checks or guess new offsets when the game updates.

## Manual installation

1. **Close the game and back up your ordinary saves.** Let normal Cloud synchronization finish, then disable Steam Cloud **for Gates of Hell** and put Steam in **Offline Mode**. Leave Steam running.
2. Obtain the release ZIP or source repository. The ZIP contains one `tactical_pause` folder; the source root contains the same files. Run the commands below from that installed folder.
3. Install the matching GOHSE `version.dll` under the game's `binaries/x64`, following the loader's instructions. **Back up any existing `version.dll`; do not overwrite an unknown proxy or another loader.** This repository does not include or install that dependency.
4. Extract the ZIP's `tactical_pause` folder into `<game>/gohse/mods/`. The resulting folder contains all of this project's runtime code and instructions:

   ```text
   tactical_pause/
   ├── mod.info
   ├── README.md
   ├── CHANGELOG.md
   ├── run_offline.py
   ├── verify_build.py
   └── resource/script/gohse/
       ├── mod.json
       └── bootstrap.lua
   ```

   When installing from a source checkout, copy only those listed files with their relative paths. Do not copy private data or the whole research workspace. This is GOHSE's local-mod directory, **not** a Steam Workshop subscription. GOHSE's DLL remains separate, beside the game executable.
5. Ensure `<game>/gohse/settings.json` exists and is valid JSON. Preserve any existing configuration. For a new installation, a minimal file is:

   ```json
   {"EnableAchievement": false, "DisableUpdates": true}
   ```

   Each supported launch mounts its own read-only settings copy, disabling loader updates and the achievement-check modification for that run. It does not rewrite the shared settings file.
6. Prepare the separate prefix **outside the mod folder**, so reinstalling/removing the code cannot erase progress. One starting point is a private copy of a working ordinary app-400750 Proton prefix, never the original directory. If the destination does not exist:

   ```bash
   prefix="$HOME/.local/share/goh-tactical-pause/compatdata"
   test ! -e "$prefix" &&
   mkdir -p -- "$HOME/.local/share/goh-tactical-pause" &&
   cp -a -- "$HOME/.steam/debian-installation/steamapps/compatdata/400750" "$prefix"
   ```

   Its game profile must be at:

   ```text
   ~/.local/share/goh-tactical-pause/compatdata/pfx/drive_c/users/steamuser/Documents/my games/gates of hell/profiles/<account-id>/
   ```

   `<account-id>` is the numeric Steam userdata account directory. The launcher discovers the account from Steam's latest connection transition, checks that it exists in local `loginusers.vdf`, and binds it for that session without printing it. Missing, ambiguous, invalid or changed connection identity is refused; no optional `MostRecent` field is assumed.

   **Check copied Documents paths.** If the copy contains a Documents symlink to your real home/profile, replace that link **in the copy only** with a real private directory and copy the needed Gates of Hell profile into it. Do not alter the ordinary prefix or point this checkout at it. The launcher rejects a symlinked prefix, overlap with the ordinary prefix, and a game-profile path resolving outside the private prefix.

   To reuse a different existing private prefix, pass `--prefix /absolute/path/to/private-compatdata` on both `--check` and normal launch. It is never moved or bundled automatically.
7. Check without launching:

   ```bash
   python3 run_offline.py --self-check
   python3 run_offline.py --check
   ```

8. Launch:

   ```bash
   python3 run_offline.py
   ```

   Wait for **`Managed tactical-pause pair verified in the isolated client.`** A zero exit status by itself is not activation evidence. Use **SINGLEPLAYER** → campaign or solo Conquest and test a disposable operation before committing playtime.

## Controls and shutdown

Use the game's existing **Pause** binding to freeze/resume. Click or box-select units while paused and issue normal orders. With the tested profile, right-click moves, Shift + right-click appends waypoints, and **F** cancels an order. Your own bindings may differ.

A passive **TACTICAL PAUSE — Orders enabled** indicator appears for paused Conquest while the game is foreground. Campaign missions keep their native indicator. No custom order recorder or replay queue is added.

Quit through the game's menu for normal saving. **Do not enable Steam Online or Cloud while this launcher runs:** a failed continuing safety check forcibly ends only the isolated session, without saving. `Ctrl+C` also stops the session. After the game and launcher exit, you can restore Online Mode and this game's Cloud toggle. Progress in the private prefix remains separate; this project does not merge it into your normal saves.

## How it works

GOHSE's managed expected-byte patches skip the balanced client pause-owner add/remove calls at RVAs `0xc73c42` and `0xc73c64`. The native server pause/resume protocol and order ownership remain in use; the extra local owner no longer locks RTS input. Global quant suppression and zero-time-scale approaches are not used.

For confirmed Conquest save/exit, verified callbacks at `0x2df1c0` and `0x2df480` request the ordinary frontend pause toggle through `0xc725e0(client, 0)` before forwarding the original confirmation. Cancelling does not request resume. Calling the client's pause acknowledgement alone would not resume the server.

The launcher binds one locally discovered Steam account for the session, verifies its offline/Cloud state and connection transition, checks the exact executable/loader and installed payload, and starts private user/network/mount namespaces. Only loopback networking and the named local Steam IPC bridges are present. The game's normal executable file is not patched on disk.

Solo Conquest internally uses `page_scene_game_multi`, multiplayer client classes and `script/multiplayer/modes/conquest.lua`, despite entry through SINGLEPLAYER. Those internal names do not mean another human joined. They also do not make multiplayer/co-op supported.

## Troubleshooting and removal

- Missing prerequisite or refused namespace/profile/hash: stop and resolve that exact prerequisite; do not remove guards. There is no automatic fallback to the ordinary prefix.
- Loader logs: `<game>/gohse/logs/`. Game log: `<private-prefix>/pfx/drive_c/users/steamuser/Documents/my games/gates of hell/log/game.log`.
- If the managed-pair message never appears, do not assume tactical pause is active. Check the installed file layout and loader log. A mismatched build is unsupported.
- To disable discovery, close the game and move `gohse/mods/tactical_pause` **outside** `gohse/mods`, or remove only that installed mod folder. Renaming its folder inside the discovery directory is not sufficient. Leave other mods and their loader alone.
- Ordinary launches without the scoped activation flag do not apply this mod's tactical-pause changes. Preserve your private saves before removing any private prefix.

## Credits, disclosure and licensing

GOHSE by [nature2468](https://github.com/nature2468/gohse) provides the native hook/managed-patch API and its LuaJIT runtime. Its dependencies, including LuaJIT and MinHook, remain subject to their own notices; none is bundled here. This project is not affiliated with the game developers, Valve or GOHSE.

Development used **OpenAI Codex GPT-6.1 Sol through OMP**, with read-only scout, code and security reviews. The behavior claims above come from actual game checks, not just generated code or static analysis. AI assistance and review do not establish that code or a third-party loader is safe.

No additional project license has been selected or granted. This is publicly available source, not a claim of MIT/Apache licensing. The game and external dependencies retain their respective rights.
