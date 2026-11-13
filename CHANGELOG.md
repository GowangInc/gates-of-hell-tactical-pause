# Changelog

## 0.4.0 — 2026-11-13

- Add a read-only-by-default shortcut installer, explicit code allowlist, private unique backups, symlink/overlap refusal and opt-in shortcut trust.
- Validate Desktop Entry escaping through a native launcher, including paths with spaces, quotes, backslashes and literal field codes.
- Add an agent-install guide and game-only README screenshots. Keep GOHSE and all profiles/saves/logs outside the download.
- Keep Steam Offline Mode, this game's Cloud toggle and their restoration manual. The shortcut runs `run_offline.py`; no automatic Steam controller is distributed.
- Reject a runtime/client exit before managed-patch activation is verified.
- The native Lua pause implementation and exact supported game/loader builds are unchanged; the gameplay evidence is from the verified 0.3.2 implementation.

## 0.3.2 — 2026-11-12

First public source release. Exact target: Gates of Hell 1.067.0 / Steam build 25492057; tested on Linux/Proton with GOHSE 0.1.1.

- Enable solo Conquest selection and native orders during true pause by excluding only the balanced local client pause-owner calls.
- Preserve ordinary single-player campaign active pause and the native order queue.
- Resume the server through the native frontend request before confirmed Conquest save/retreat. Cancelling confirmation preserves pause.
- Add an isolated-offline launcher, passive Conquest pause indicator, exact executable/loader guards, installed-payload parity checks and owned-runtime shutdown.
- Discover the current Steam account from the latest connection transition, cross-check local login metadata and bind it for the session instead of embedding a personal ID; reject missing, ambiguous, invalid or changed identities.
- Verify the actual executable selected by the launcher; resolve the verifier's default relative to the current home; handle an absent ordinary prefix in overlap checks.
- Handle short process-memory reads during normal client exit.
- Package the payload, launcher, verifier and instructions in one `tactical_pause` folder; keep private Proton state outside it by default, with `--prefix` for an existing separate copy.

Verified in-game: distinct paused orders and resume, camera control, replacement/cancellation/Shift-waypoints, held-trigger SMG freeze, native campaign active pause, confirmed paused-retreat save and operation reload, managed rollback and normal shutdown. The last native gameplay run used the same Lua payload as this release; subsequent publication changes are launcher account/path handling and documentation.

No game files, dependency DLLs, saves, logs, recordings or Proton prefix are distributed. Multiplayer/co-op, Windows installation, other game versions, all action/weapon combinations and manual save/load inside a paused mission are not established.
