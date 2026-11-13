# Agent-assisted installation

## Copy-paste prompt

```text
Help me install and safely test this Gates of Hell tactical-pause package on my Linux/X11 system. Read AGENT_INSTALL.md, README.md and the source first. Inspect the real installation; do not guess versions, offsets, hashes, paths or Steam IPC ports. Steam setup and restoration are manual in this release. Ask me before installing the loader or project files, changing shortcut trust/permissions, changing Steam settings or launching gameplay. Record the initial Steam settings and restore only what changes, after the isolated game stops. Do not touch my ordinary saves/prefix, collect credentials, weaken security, enable debugging listeners or publish private IDs, saves or logs. Stop on unsupported or unverified conditions.
```

An agent may perform read-only inspection without treating that as permission to install or launch. Human approval is required for the consequential actions below.

## 1. Inspect the actual installation

Read `README.md`, `install_shortcut.py`, `run_offline.py`, `verify_build.py` and the Lua payload. GOHSE loads native code; neither Lua nor the private Proton prefix is a sandbox. Single-player campaign and solo Conquest only: no multiplayer, co-op or protected sessions.

Confirm Linux/X11, Python 3.9+ with Tk, and the commands/namespace permissions listed in the README. The shortcut helper additionally uses `xdg-user-dir`; explicit shortcut trust and its optional native-parser self-check use `gio`. Do not weaken OS security if a requirement is refused.

The tested layout has Steam at `~/.steam/debian-installation`, with Gates of Hell, Proton Experimental and `SteamLinuxRuntime_sniper` in that library. Confirm the existing host-loopback Steam IPC endpoints are `57343`, `18183` and `27667`. These are measured values, not universal defaults. Stop if the layout/runtime/IPC differs; do not guess replacements, forward gameplay traffic or substitute remote endpoints.

Verify the actual executable with `verify_build.py` and the requirements in the README. Supported: **GoH 1.067.0 / Steam build 25492057**, client SHA-256 `4b6a807ad867c4f6eb1019376224d74fa3a6ac048355739ab0b76d73c7c0a267`; **GOHSE 0.1.1**, `version.dll` SHA-256 `8664a225b0615992834f7408d58ff1ae5df1c9e9eff8811d8e7c0f44f4d1c426`. Never update offsets or remove guards to accept a mismatch.

GOHSE is separate and is not installed by this package. Obtain it from its own 0.1.1 release, review its notices, and obtain human approval before installing it beside the game executable. Preserve and stop at any unknown existing `binaries/x64/version.dll`; never overwrite another proxy/loader. Never disable anti-cheat, DRM or server checks.

## 2. Prepare private game data

Close the game, let ordinary Cloud synchronization finish, and back up ordinary saves. Record the initial Steam Online/Offline state and this game's Cloud toggle before changing either.

With approval, make a real private copy of the ordinary app-400750 Proton `compatdata`, outside the mod folder. The default destination is `~/.local/share/goh-tactical-pause/compatdata`. Never overwrite, refresh or merge an existing destination. After checking the exact source/destination paths:

```bash
src="$HOME/.steam/debian-installation/steamapps/compatdata/400750"
dst="$HOME/.local/share/goh-tactical-pause/compatdata"
test -d "$src" && test ! -e "$dst" && mkdir -p "$(dirname "$dst")" && cp -a -- "$src" "$dst"
```

Inspect the **copy** for Documents symlinks into ordinary home/profile data. Obtain approval for the exact copied link before replacing it with a real private directory and copying the required Gates of Hell profile into it. Do not alter or remove ordinary data. The launcher rejects an overlapping ordinary prefix and a game-profile path escaping the private prefix. Keep locally derived account identifiers private. Private progress is never merged into normal saves.

## 3. Install the code and shortcut

From the downloaded package or source checkout, inspect the installer and check its destinations:

```bash
python3 install_shortcut.py --check
```

For another existing private prefix, pass `--prefix /absolute/path/to/private-compatdata` to the installer and subsequent launcher commands. This check validates paths/project-file destinations; it does not replace the build/dependency inspection above or the guarded launch check below.

With human approval:

```bash
python3 install_shortcut.py --install
```

The helper copies only its explicit project-file allowlist into `<game>/gohse/mods/tactical_pause` and creates a desktop shortcut targeting `run_offline.py`. Changed project files receive private, uniquely named backups. Unrelated/unmarked shortcuts and symlinked destinations are refused; do not bypass that refusal. The helper does not install GOHSE, create a prefix, launch a game or change Steam.

Only add `--trust-shortcut` after explicit approval to make the shortcut executable and trusted. Otherwise the human can review and use the desktop's Allow Launching action. Preserve existing GOHSE settings; follow the README's settings-file requirement rather than replacing a user's configuration.

## 4. Prepare Steam manually, then check and launch

There is **no automatic Steam controller or restoration tool in this release**. Close other running Steam games before changing the whole client's mode. Obtain explicit approval, then use the normal Steam UI:

1. Gates of Hell → Properties → General: turn Cloud OFF **for this game only**.
2. Steam → Go Offline: complete the real mode transition and leave Steam running.

Do not edit login/config files, change other games' settings or add debugging listeners. If the UI cannot be controlled reliably, stop and let the human perform these steps; do not guess clicks or claim a completed transition.

Check without launching:

```bash
python3 run_offline.py --self-check
python3 run_offline.py --check
```

Use the same `--prefix` if needed. Stop on any failed check. With human approval, launch via the shortcut or `python3 run_offline.py`.

Success requires `Managed tactical-pause pair verified in the isolated client.` and actual gameplay behavior in a disposable private operation: frozen simulation, selection/orders during pause, then execution on resume. Exit status alone is not proof. Native pause behavior was verified with the 0.3.2 Lua implementation, unchanged in this release; do not infer coverage of every weapon/action, mod combination or manual save/load inside an actively paused mission.

## 5. Shut down and restore manually

Quit through the game's menu for normal saving. Wait for **both the game and launcher to stop**, then restore only the settings changed from the recorded baseline: return Online if needed, then restore this game's original Cloud toggle. Do not enable Online/Cloud while the isolated game runs; the guard ends that disposable session without saving. `Ctrl+C` also stops it. Never merge private progress into ordinary saves automatically.

Stop on unsupported platform/layout/runtime/IPC/hash, missing prerequisites, an unknown loader, unsafe paths, unreliable UI or missing human approval. Preserve private data and explain the exact failure; never bypass a guard or describe unverified automation as working.
