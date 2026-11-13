# Agent-assisted installation

## Copy-paste prompt

```text
Help me install and safely test this Gates of Hell tactical-pause package. Read AGENT_INSTALL.md, README.md and the source first. Inspect the real installation; do not guess versions, offsets, hashes or paths. Ask me before installing the loader or project files, changing permissions or launching gameplay. Do not touch ordinary saves, collect credentials, weaken security, enable debugging listeners or publish private IDs, saves or logs. Stop on unsupported or unverified conditions.
```

An agent may perform read-only inspection without treating that as permission to install or launch. Human approval is required before installing files or launching gameplay.

## 1. Inspect the actual installation

Read `README.md`, `verify_build.py`, `enable.py` and the Lua payload. GOHSE loads native code; Lua is not a sandbox. Do not disable anti-cheat, DRM or server checks.

Supported build: **GoH 1.067.0 / Steam build 25492057**, client SHA-256 `4b6a807ad867c4f6eb1019376224d74fa3a6ac048355739ab0b76d73c7c0a267`; **GOHSE 0.1.1**, `version.dll` SHA-256 `8664a225b0615992834f7408d58ff1ae5df1c9e9eff8811d8e7c0f44f4d1c426`. Run `python3 verify_build.py` to verify the default discovered executable, or pass its path explicitly. Never update offsets or remove guards to accept a mismatch.

GOHSE is separate and is not installed by this package. Obtain it from its own 0.1.1 release, review its notices, and obtain human approval before installing it beside the game executable. Preserve and stop at any unknown existing `version.dll`; never overwrite another proxy/loader.

## 2. Prepare personal data safely

Close the game and back up ordinary saves. Steam Offline Mode and Cloud OFF for this game are optional recommendations, not requirements. They must not be treated as protection from the marker's effect in multiplayer.

## 3. Install and opt in

With approval, install GOHSE's `version.dll` beside `call_to_arms.exe` (under `binaries/x64`) and extract the `tactical_pause` folder into `<game>/gohse/mods/`, creating `<game>/gohse/mods/tactical_pause/`. Do not overwrite an unknown DLL or copy private data/research files.

From the installed mod folder, run:

```bash
python3 enable.py
```

The helper locates the client using `verify_build.py`'s path logic, checks its exact SHA-256 and writes `enable-tactical-pause` in the mod folder with exactly this content and a final newline. If Steam stores the game in a custom library the helper cannot find, pass the executable explicitly: `python3 enable.py --client "PATH/TO/steamapps/common/Call to Arms - Gates of Hell/binaries/x64/call_to_arms.exe"`.

```text
4b6a807ad867c4f6eb1019376224d74fa3a6ac048355739ab0b76d73c7c0a267
```

If creating the marker manually, use that exact content. The marker is persistent and activates this mod in **every battle** on that matching build. Multiplayer/co-op are unsupported and must not be joined while it is active. Remove the marker when activation is no longer wanted.

## 4. Start via Steam

- **Windows native:** start Gates of Hell via Steam; no DLL override is needed. Windows setup is documented but runtime-unverified until a real Windows test. Do not describe Windows behavior as verified.
- **Linux/Proton:** add this one-time Steam launch option and start via Steam:

  ```text
  WINEDLLOVERRIDES=version=n,b %command%
  ```

Steam Offline Mode and Cloud OFF are optional recommendations. The isolated developer launcher `run_offline.py` remains available for testing; it is not part of the ordinary opt-in user flow. Verify gameplay only in a disposable single-player campaign or solo Conquest operation.

## 5. Stop and remove

Quit through the game's menu. To disable the feature, remove `gohse/mods/tactical_pause/enable-tactical-pause`. To remove the mod, close the game and move `gohse/mods/tactical_pause` outside `gohse/mods`. Leave other mods and their loader alone. Preserve ordinary saves and never merge private test data automatically.

Stop on unsupported platform/build/hash, missing prerequisites, an unknown loader, unsafe paths or missing human approval. Preserve data and explain the exact failure; never bypass a guard or describe unverified automation as working.
