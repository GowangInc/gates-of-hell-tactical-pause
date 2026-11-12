#!/usr/bin/env python3
"""Guarded Linux/Proton launcher: offline single-player campaign and solo Conquest."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
STEAM = Path.home() / ".steam/debian-installation"
GAME = STEAM / "steamapps/common/Call to Arms - Gates of Hell"
CLIENT = GAME / "binaries/x64/call_to_arms.exe"
PREFIX = Path.home() / ".local/share/goh-tactical-pause/compatdata"
STEAM_ID_BASE = 76561197960265728
# Bound once by main(); polling must not silently switch the session's account.
ACCOUNT = None
STEAM_ID = None
SHARED_CONFIG = None
SETTINGS = GAME / "gohse/settings.json"
INSTALLED = GAME / "gohse/mods/tactical_pause/resource/script/gohse"
SOURCE = ROOT / "resource/script/gohse"
PORTS = (57343, 18183, 27667)  # Existing Steam IPC endpoints; no host TCP listener.
SITES = (0xC73C42, 0xC73C64)
LOADER_SHA256 = "8664a225b0615992834f7408d58ff1ae5df1c9e9eff8811d8e7c0f44f4d1c426"


def parse_vdf(text):
    tokens = []
    lexer = re.compile(r'\s+|//[^\n]*|"((?:\\.|[^"\\])*)"|([{}])')
    offset = 0
    while offset < len(text):
        match = lexer.match(text, offset)
        if match is None:
            raise ValueError("unsupported or malformed VDF syntax")
        if match.group(1) is not None or match.group(2):
            tokens.append(match.group(1) if match.group(1) is not None else match.group(2))
        offset = match.end()
    iterator = iter(tokens)

    def section(nested=False):
        result = {}
        for key in iterator:
            if key == "}":
                if not nested:
                    raise ValueError("unexpected VDF closing brace")
                return result
            if key == "{":
                raise ValueError("unexpected VDF opening brace")
            value = next(iterator)
            if value == "}":
                raise ValueError("missing VDF value")
            result[key.casefold()] = section(True) if value == "{" else value
        if nested:
            raise ValueError("unclosed VDF section")
        return result

    return section()


def cloud_disabled(config):
    try:
        app = config["userroamingconfigstore"]["software"]["valve"]["steam"]["apps"]["400750"]
        return app.get("cloudenabled") == "0"
    except (KeyError, TypeError):
        return False  # Missing is Steam's enabled/default state, not consent.


def last_steam_transition():
    # Never print the surrounding private authentication log data.
    with (STEAM / "logs/connection_log.txt").open("rb") as stream:
        stream.seek(max(0, stream.seek(0, 2) - 65536))
        lines = stream.read().decode("utf-8", errors="replace").splitlines()
    return next((line for line in reversed(lines) if any(word in line for word in
                 ("LogOff()", "[Connecting,", "[Logging On,", "RecvMsgClientLogOnResponse()"))), "")


def current_steam_id(users, transition):
    accounts = re.findall(r"\[U:1:([0-9]+)\]", transition)
    if len(accounts) != 1:
        raise RuntimeError("Steam's connection log has no unambiguous current account.")
    account = int(accounts[0])
    if not 0 < account < 2**32:
        raise RuntimeError("The selected Steam account ID is invalid.")
    steam_id = str(STEAM_ID_BASE + account)
    if not isinstance(users.get(steam_id), dict):
        raise RuntimeError("The current Steam account is absent from loginusers.vdf.")
    return steam_id


def safety_check():
    users = parse_vdf((STEAM / "config/loginusers.vdf").read_text())["users"]
    transition = last_steam_transition()
    if current_steam_id(users, transition) != STEAM_ID:
        raise RuntimeError("Steam account changed; refusing the session.")
    if users[STEAM_ID].get("wantsofflinemode") != "1":
        raise RuntimeError("Put Steam in Offline Mode first; this launcher never changes account settings.")
    if not cloud_disabled(parse_vdf(SHARED_CONFIG.read_text())):
        raise RuntimeError("Turn off Steam Cloud for Gates of Hell first.")
    if "LogOff()" not in transition or f"[U:1:{ACCOUNT}]" not in transition:
        raise RuntimeError("Steam's connection log does not establish an offline current account.")


def namespace(pid):
    return os.readlink(f"/proc/{pid}/ns/net")


def loopback_only(pid):
    rows = Path(f"/proc/{pid}/net/dev").read_text().splitlines()[2:]
    interfaces = [row.split(":", 1)[0].strip() for row in rows if ":" in row]
    return interfaces == ["lo"]


def candidates():
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if (entry / "comm").read_text().strip() == "call_to_arms.ex":
                yield int(entry.name)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue


def signal_namespace(owned_namespace, sig):
    """Signal only processes in this launcher's new, retained namespace."""
    if owned_namespace is None:
        return
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        handle = None
        try:
            pid = int(entry.name)
            if namespace(pid) != owned_namespace:
                continue
            handle = os.pidfd_open(pid)
            if namespace(pid) == owned_namespace:
                signal.pidfd_send_signal(handle, sig)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
        finally:
            if handle is not None:
                os.close(handle)


def wine_prefix(pid):
    # Steam rewrites STEAM_COMPAT_DATA_PATH in the Windows child to its normal
    # app metadata. Proton's WINEPREFIX is the actual live profile directory.
    environment = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    value = next((item[11:] for item in environment if item.startswith(b"WINEPREFIX=")), None)
    return Path(os.fsdecode(value)).resolve() if value is not None else None


def prerequisites():
    safety_check()
    if not PREFIX.is_dir() or PREFIX.resolve() != PREFIX.absolute():
        raise RuntimeError("The existing disposable prefix must be a real, non-symlinked directory.")
    normal = (STEAM / "steamapps/compatdata/400750").resolve()
    lab = PREFIX.resolve()
    if normal == lab or normal.is_relative_to(lab) or lab.is_relative_to(normal) or (normal.exists() and normal.samefile(lab)):
        raise RuntimeError("The disposable prefix overlaps the normal Steam profile.")
    profile = PREFIX / f"pfx/drive_c/users/steamuser/Documents/my games/gates of hell/profiles/{ACCOUNT}"
    if not profile.is_dir() or not profile.resolve().is_relative_to(lab):
        raise RuntimeError("The disposable Documents/profile path escapes its prefix.")
    for binary in ("socat", "unshare", "mount", "bash", "ip", "xdotool"):
        if shutil.which(binary) is None:
            raise RuntimeError(f"Required installed tool is missing: {binary}")
    subprocess.run([sys.executable, str(ROOT / "verify_build.py"), str(CLIENT)], check=True)
    if hashlib.sha256((GAME / "binaries/x64/version.dll").read_bytes()).hexdigest() != LOADER_SHA256:
        raise RuntimeError("Installed GOHSE loader does not match the approved 0.1.1 release.")
    for filename in ("bootstrap.lua", "mod.json"):
        if (INSTALLED / filename).read_bytes() != (SOURCE / filename).read_bytes():
            raise RuntimeError(f"Installed mod differs from this workspace: {filename}")
    if not SETTINGS.is_file():
        raise RuntimeError("Existing GOHSE settings are missing; refusing an untracked configuration change.")
    # Do not let another game/process share this disposable prefix.
    for pid in candidates():
        try:
            profile = wine_prefix(pid)
        except (FileNotFoundError, ProcessLookupError):
            continue
        if profile == (PREFIX / "pfx").resolve():
            raise RuntimeError("The disposable prefix already has a running game. Close that test first.")


def self_check():
    text = '// comment\n"Root" { "Quoted" "a { brace }" "Nested" { "Flag" "0" } }'
    assert parse_vdf(text)["root"]["quoted"] == "a { brace }"
    assert parse_vdf(text)["root"]["nested"]["flag"] == "0"
    for broken in ('"Root" { "Flag" "0"', '}', '"Root" { "Flag" }',
                   '"Root" { @ "Flag" "0" }', '"Root" { "Flag" "0" } junk'):
        try:
            parse_vdf(broken)
        except (ValueError, StopIteration):
            pass
        else:
            raise AssertionError("malformed configuration was accepted")
    prefix = '"UserRoamingConfigStore" { "Software" { "Valve" { "Steam" { "Apps" {'
    suffix = '} } } } }'
    assert cloud_disabled(parse_vdf(prefix + '"400750" { "CloudEnabled" "0" }' + suffix))
    assert not cloud_disabled(parse_vdf(prefix + '"400750" { "CloudEnabled" "1" }' + suffix))
    assert not cloud_disabled(parse_vdf(prefix + '"7" { "CloudEnabled" "0" }' + suffix))
    assert not cloud_disabled({})
    current = str(STEAM_ID_BASE + 42)
    known = {str(STEAM_ID_BASE + 43): {}, current: {}}
    transition = "[U:1:42] LogOff()"
    assert current_steam_id(known, transition) == current
    for users, line in (({}, transition), (known, ""),
                        (known, "[U:1:42] [U:1:43] LogOff()"),
                        (known, "[U:1:0] LogOff()"),
                        (known, f"[U:1:{2**32}] LogOff()"),
                        (known, "[U:1:44] LogOff()")):
        try:
            current_steam_id(users, line)
        except RuntimeError:
            pass
        else:
            raise AssertionError("missing, ambiguous or invalid Steam account was accepted")
    print("PASS: VDF boundaries, account selection and app-specific Cloud refusal")


def xdo(*args):
    return subprocess.check_output(["xdotool", *map(str, args)], text=True, stderr=subprocess.DEVNULL).strip()


def run():
    import tkinter as tk

    prerequisites()
    os.environ.setdefault("DISPLAY", ":0")
    lock = (PREFIX / "tactical-pause.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    hud = tk.Tk()
    hud.withdraw()
    hud.overrideredirect(True)
    hud.attributes("-topmost", True)
    label = tk.Label(hud, text="TACTICAL PAUSE\nOrders enabled — Pause to resume",
                     font=("Sans", 12, "bold"), bg="#241f18", fg="#f1d69a", padx=14, pady=6,
                     takefocus=False)
    label.pack()
    test_settings = json.loads(SETTINGS.read_bytes())
    test_settings.update(CreateConsole=False, DisableUpdates=True, EnableAchievement=False)
    owned_settings = (json.dumps(test_settings, indent=2) + "\n").encode()
    bridges = []
    game = None
    memory = None
    client_handle = None
    client_pid = None
    base = None
    game_window = None
    error = None
    unsafe = False
    last_safety = 0.0
    last_hud = 0.0
    started = time.monotonic()
    host_namespace = namespace("self")
    # Keep sockets in a private directory. No existing user paths are removed.
    socket_dir = Path(tempfile.mkdtemp(prefix="goh-tactical-pause-"))
    private_settings = socket_dir / "settings.json"
    private_settings.write_bytes(owned_settings)
    owned_namespace = None
    namespace_handle = None
    mod_reported = False

    def stop(_signal=None, _frame=None):
        raise KeyboardInterrupt

    def poll():
        nonlocal memory, client_handle, client_pid, base, game_window, error, unsafe, last_safety, last_hud, mod_reported
        try:
            now = time.monotonic()
            if now - last_safety >= 1:
                try:
                    safety_check()
                except Exception:
                    unsafe = True
                    raise RuntimeError("Safety stop: Steam/Cloud left the offline setup. Ending only the isolated test, without saving.")
                last_safety = now
            exit_code = game.poll()
            if exit_code is not None:
                if exit_code != 0:
                    raise RuntimeError(f"Isolated runtime exited with status {exit_code}; inspect the game/GOHSE logs.")
                hud.quit()
                return
            if client_handle is not None and select.select([client_handle], [], [], 0)[0]:
                hud.quit()
                return
            if memory is None:
                for pid in candidates():
                    try:
                        if namespace(pid) != owned_namespace:
                            continue
                        if not loopback_only(pid):
                            raise RuntimeError("Game has a non-loopback network interface; refusing the session.")
                        if wine_prefix(pid) != (PREFIX / "pfx").resolve():
                            raise RuntimeError("Unexpected profile in the isolated game process.")
                        maps = Path(f"/proc/{pid}/maps").read_text().splitlines()
                        header = next((line for line in maps if line.endswith(str(CLIENT)) and line.split()[2] == "00000000"), None)
                        if header is None:
                            continue
                        candidate_memory = os.open(f"/proc/{pid}/mem", os.O_RDONLY)
                        try:
                            candidate_handle = os.pidfd_open(pid)
                        except OSError:
                            os.close(candidate_memory)
                            continue
                        base = int(header.split("-", 1)[0], 16)
                        memory, client_handle, client_pid = candidate_memory, candidate_handle, pid
                        break
                    except (FileNotFoundError, ProcessLookupError, PermissionError):
                        continue
                if memory is None and now - started > 120:
                    raise RuntimeError("No isolated game client appeared; inspect the existing game log.")
            if memory is not None:
                patched = all(os.pread(memory, 5, base + site) == b"\x90" * 5 for site in SITES)
                if not patched and not mod_reported and now - started > 120:
                    raise RuntimeError("Managed tactical-pause patches did not activate; refusing to advertise a working pause.")
                if patched and not mod_reported:
                    print("Managed tactical-pause pair verified in the isolated client.", flush=True)
                    mod_reported = True
                try:
                    client = struct.unpack("<Q", os.pread(memory, 8, base + 0x15A4F00))[0]
                    state = struct.unpack("<I", os.pread(memory, 4, client + 0x244))[0] if client else 0
                except (OSError, struct.error):
                    state = 0  # No live scene context during a mission transition.
                if now - last_hud >= .4:
                    last_hud = now
                    windows = xdo("search", "--onlyvisible", "--pid", client_pid, "--name", "GATES OF HELL").splitlines()
                    game_window = int(windows[-1]) if windows else None
                    visible = patched and state == 1 and game_window is not None and int(xdo("getactivewindow")) == game_window
                    if visible:
                        geometry = dict(line.split("=", 1) for line in xdo("getwindowgeometry", "--shell", game_window).splitlines())
                        x = int(geometry["X"]) + (int(geometry["WIDTH"]) - label.winfo_reqwidth()) // 2
                        y = int(geometry["Y"]) + 85
                        hud.geometry(f"+{x}+{y}")
                        hud.deiconify()
                        hud.lift()
                    else:
                        hud.withdraw()
        except (FileNotFoundError, ProcessLookupError, subprocess.CalledProcessError):
            game_window = None
            hud.withdraw()  # Window/process can change briefly while a mode loads.
        except Exception as exc:
            error = str(exc)
            hud.quit()
            return
        hud.after(100, poll)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        for port in PORTS:
            sock = socket_dir / f"steam-{port}.sock"
            bridges.append(subprocess.Popen(
                ["socat", f"UNIX-LISTEN:{sock},fork,mode=0600", f"TCP:127.0.0.1:{port}"],
                start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        deadline = time.monotonic() + 5
        while not all((socket_dir / f"steam-{port}.sock").exists() for port in PORTS):
            if any(p.poll() is not None for p in bridges) or time.monotonic() >= deadline:
                raise RuntimeError("Steam IPC bridge failed to start.")
            time.sleep(.02)
        ready_read, ready_write = os.pipe()
        continue_read, continue_write = os.pipe()
        # The child waits before starting descendants. If startup is interrupted,
        # pipe EOF exits the child instead of leaving an undiscovered game.
        commands = [
            f"printf R >&{ready_write}; exec {ready_write}>&-;",
            f"read -r ready <&{continue_read} || exit 1; exec {continue_read}<&-;",
            "ip link set lo up || exit 1;",
            f"mount --bind {shlex.quote(str(private_settings))} {shlex.quote(str(SETTINGS))} || exit 1;",
            f"mount -o remount,bind,ro {shlex.quote(str(SETTINGS))} || exit 1;",
        ]
        commands += [f"socat TCP-LISTEN:{p},bind=127.0.0.1,fork,reuseaddr UNIX-CONNECT:{shlex.quote(str(socket_dir / f'steam-{p}.sock'))} &" for p in PORTS]
        # Check inside the new namespace, before enabling the Lua entry point.
        commands.append("test \"$(ip -o link show | wc -l)\" -eq 1 || exit 1;")
        commands.append("export OMP_GOH_OFFLINE_TACTICAL_PAUSE=1;")
        runtime = STEAM / "steamapps/common/SteamLinuxRuntime_sniper/_v2-entry-point"
        proton = STEAM / "steamapps/common/Proton - Experimental/proton"
        commands.append("exec " + shlex.join([str(runtime), "--verb=waitforexitandrun", "--", str(proton), "run", str(CLIENT)]))
        shell = " ".join(commands)
        environment = os.environ.copy()
        environment.update(WINEDLLOVERRIDES="version=n,b", STEAM_COMPAT_DATA_PATH=str(PREFIX),
                           STEAM_COMPAT_CLIENT_INSTALL_PATH=str(STEAM), SteamAppId="400750", SteamGameId="400750")
        print("Starting isolated single-player campaign / solo Conquest. Use Pause and normal order controls.", flush=True)
        print("Do not enable Steam Online/Cloud while running: the safety guard ends this disposable game without saving.", flush=True)
        print("Ctrl+C ends the test session. Normal Steam launches do not activate this mod.", flush=True)
        with os.fdopen(ready_read, "rb", buffering=0) as ready, \
                os.fdopen(ready_write, "wb", buffering=0) as sender, \
                os.fdopen(continue_read, "rb", buffering=0) as receiver, \
                os.fdopen(continue_write, "wb", buffering=0) as proceed:
            game = subprocess.Popen(
                ["unshare", "-Urnm", "--propagation", "private", "bash", "-c", shell],
                cwd=GAME, env=environment, pass_fds=(ready_write, continue_read),
                start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sender.close()
            receiver.close()
            if not select.select([ready], [], [], 5)[0] or ready.read(1) != b"R":
                raise RuntimeError("Isolated namespace did not initialize.")
            owned_namespace = namespace(game.pid)
            if owned_namespace == host_namespace:
                raise RuntimeError("Namespace setup failed; refusing to start the game.")
            namespace_handle = os.open(f"/proc/{game.pid}/ns/net", os.O_RDONLY)
            proceed.write(b"continue\n")
        hud.after(100, poll)
        hud.mainloop()
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        hud.withdraw()
        if client_handle is not None:
            try:
                signal.pidfd_send_signal(client_handle, signal.SIGKILL if unsafe else signal.SIGTERM)
            except ProcessLookupError:
                pass
            os.close(client_handle)
        # Wine can start new process groups. Namespace membership, retained above
        # before any descendant starts, remains the ownership boundary for all.
        signal_namespace(owned_namespace, signal.SIGKILL if unsafe else signal.SIGTERM)
        if game is not None:
            if game.poll() is None:
                try:
                    os.killpg(game.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                game.wait(timeout=2)
            except subprocess.TimeoutExpired:
                signal_namespace(owned_namespace, signal.SIGKILL)
                try:
                    os.killpg(game.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                game.wait()
        signal_namespace(owned_namespace, signal.SIGKILL)
        for bridge in bridges:
            try:
                os.killpg(bridge.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                bridge.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(bridge.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                bridge.wait()
        if memory is not None:
            os.close(memory)
        if namespace_handle is not None:
            os.close(namespace_handle)
        hud.destroy()
        lock.close()
    if error:
        raise RuntimeError(error)


def main():
    global ACCOUNT, STEAM_ID, SHARED_CONFIG, PREFIX

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify prerequisites without launching")
    parser.add_argument("--self-check", action="store_true", help="check configuration guard boundaries without touching Steam")
    parser.add_argument("--prefix", type=Path, default=PREFIX,
                        help="existing separate Proton compatdata directory; never the ordinary Steam prefix")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    PREFIX = args.prefix.expanduser().absolute()
    STEAM_ID = current_steam_id(
        parse_vdf((STEAM / "config/loginusers.vdf").read_text())["users"], last_steam_transition())
    ACCOUNT = int(STEAM_ID) - STEAM_ID_BASE
    SHARED_CONFIG = STEAM / f"userdata/{ACCOUNT}/7/remote/sharedconfig.vdf"
    if args.check:
        prerequisites()
        print("PASS: exact build, installed mod, offline Steam and disabled app Cloud")
    else:
        run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Isolated tactical-pause session stopped.", file=sys.stderr)
    except (OSError, ValueError, KeyError, StopIteration, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
