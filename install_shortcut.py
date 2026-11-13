#!/usr/bin/env python3
"""Install the tactical-pause payload and a desktop launcher (no game launch)."""

import argparse
import filecmp
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import run_offline as runner

ROOT = Path(__file__).resolve().parent
MOD = runner.GAME / "gohse/mods/tactical_pause"
DESKTOP_NAME = "Gates of Hell Tactical Pause.desktop"
OWNERSHIP = "X-GOH-Tactical-Pause=1"
MANIFEST = (
    "README.md",
    "CHANGELOG.md",
    "AGENT_INSTALL.md",
    "mod.info",
    "install_shortcut.py",
    "run_offline.py",
    "verify_build.py",
    "resource/script/gohse/bootstrap.lua",
    "resource/script/gohse/mod.json",
    "docs/images/conquest-paused-orders.png",
    "docs/images/conquest-resumed-orders.png",
)


def desktop_quote(value):
    """Quote one argument for Desktop Entry Exec (not shell syntax)."""
    value = os.fspath(value)
    if any(ch in value for ch in "\n\r\x00"):
        raise ValueError("desktop command argument contains a newline or NUL")
    # Exec quoting: escape backslashes, double quotes, backticks and dollar signs.
    escaped = "".join("\\" + ch if ch in '\\"`$' else ch for ch in value)
    return '"' + escaped + '"'


def desktop_file_escape(value):
    """Escape string values using the Desktop Entry string-value rules."""
    return (value.replace("\\", "\\\\").replace("\n", "\\n")
            .replace("\t", "\\t").replace("\r", "\\r"))


def exec_line(argv):
    # Percent field codes are not permitted in arguments; encode '%' as '%%'.
    return " ".join(desktop_quote(os.fspath(arg).replace("%", "%%")) for arg in argv)


def desktop_contents(mod, prefix):
    python = shutil.which("python3") or "python3"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=" + desktop_file_escape("Gates of Hell Tactical Pause") + "\n"
        "Comment=" + desktop_file_escape("First disable Gates of Hell Cloud and put Steam in Offline Mode; then launch the isolated session.") + "\n"
        "Icon=steam\nTerminal=true\n"
        + OWNERSHIP + "\n"
        "Exec=" + desktop_file_escape(exec_line([python, str(mod / "run_offline.py"), "--prefix", str(prefix)])) + "\n"
    )


def desktop_dir():
    try:
        raw = subprocess.check_output(["xdg-user-dir", "DESKTOP"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("cannot resolve Desktop; install/use xdg-user-dir") from exc
    path = Path(raw).expanduser()
    if not raw or not path.is_absolute() or not path.is_dir():
        raise RuntimeError("xdg-user-dir DESKTOP must resolve to an existing directory")
    resolved = path.resolve()
    if resolved == Path.home().resolve():
        raise RuntimeError("home directory cannot be used as Desktop")
    return resolved


def no_symlink_components(path):
    path = Path(path).absolute()
    cursor = Path(path.anchor)
    for component in path.parts[1:]:
        cursor /= component
        if cursor.is_symlink():
            raise RuntimeError(f"refusing symlinked path: {cursor}")


def checked_prefix(raw):
    path = Path(raw).expanduser().absolute()
    no_symlink_components(path)
    if not path.is_dir():
        raise RuntimeError(f"prefix must be an existing directory: {path}")
    resolved = path.resolve()
    ordinary = (runner.STEAM / "steamapps/compatdata/400750").resolve()
    if resolved == ordinary or ordinary in resolved.parents or resolved in ordinary.parents:
        raise RuntimeError("prefix must be a private copy, not the ordinary Steam compatdata prefix")
    if resolved == MOD.resolve() or MOD.resolve() in resolved.parents or resolved in MOD.resolve().parents:
        raise RuntimeError("prefix must be outside the installed mod folder")
    return resolved


def ensure_owned_target():
    no_symlink_components(MOD)
    if not MOD.exists():
        return
    if not MOD.is_dir():
        raise RuntimeError(f"mod target is not a directory: {MOD}")
    marker = MOD / "resource/script/gohse/mod.json"
    no_symlink_components(marker)
    if any(MOD.iterdir()):
        if not marker.is_file():
            raise RuntimeError(f"refusing nonempty unrelated mod target: {MOD}")
        import json
        try:
            ownership = json.loads(marker.read_text(encoding="utf-8")).get("id")
        except (OSError, ValueError, AttributeError):
            ownership = None
        if ownership != "omp.tactical-pause":
            raise RuntimeError(f"refusing nonempty unrelated mod target: {MOD} (ownership marker mismatch)")


def backup_file(path):
    directory = Path.home() / ".local/share/goh-tactical-pause/backups"
    no_symlink_components(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
        raise RuntimeError("backup directory must be owned, private and not symlinked")
    fd, _ = tempfile.mkstemp(prefix=path.name + ".", dir=directory)
    with os.fdopen(fd, "wb") as backup, path.open("rb") as source:
        shutil.copyfileobj(source, backup)


def validate_payload():
    ensure_owned_target()
    for rel in MANIFEST:
        src, dst = ROOT / rel, MOD / rel
        no_symlink_components(src)
        no_symlink_components(dst)
        if not src.is_file():
            raise RuntimeError(f"required project file is missing: {src}")
        if dst.exists() and not dst.is_file():
            raise RuntimeError(f"project file destination is not a regular file: {dst}")


def copy_payload():
    validate_payload()
    for rel in MANIFEST:
        src, dst = ROOT / rel, MOD / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and filecmp.cmp(src, dst, shallow=False):
            continue
        if dst.exists():
            backup_file(dst)
        shutil.copy2(src, dst)


def validate_desktop(entry):
    no_symlink_components(entry)
    if not entry.exists():
        return
    if not entry.is_file():
        raise RuntimeError(f"desktop entry path is not a regular file: {entry}")
    text = entry.read_text(encoding="utf-8")
    if OWNERSHIP not in text.splitlines():
        raise RuntimeError(f"refusing unrelated or unmarked desktop entry: {entry}")


def install_shortcut(prefix, trust):
    directory = desktop_dir()
    entry = directory / DESKTOP_NAME
    contents = desktop_contents(MOD, prefix)
    validate_desktop(entry)
    if not entry.exists() or entry.read_text(encoding="utf-8") != contents:
        if entry.exists():
            backup_file(entry)
        fd, temporary = tempfile.mkstemp(prefix=".goh-tactical-pause-", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(contents)
            os.replace(temporary, entry)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    if trust:
        os.chmod(entry, 0o755)
        subprocess.run(["gio", "set", str(entry), "metadata::trusted", "true"], check=True)


def self_check():
    import json
    # Exercise the native Desktop Entry consumer, including its string-value and
    # Exec argument decoding, rather than comparing our own generated text.
    with tempfile.TemporaryDirectory(prefix="goh-shortcut-check-") as temporary:
        folder = Path(temporary) / 'mod $dollar`tick`"quote\\slash%percent'
        folder.mkdir()
        (folder / "run_offline.py").write_text("import json, sys; print(json.dumps(sys.argv[1:]))\n")
        prefix = Path(temporary) / 'private $dollar`tick`"quote\\slash%f %u'
        entry = Path(temporary) / "check.desktop"
        entry.write_text(desktop_contents(folder, prefix).replace("Terminal=true\n", "Terminal=false\n"))
        result = subprocess.run(["gio", "launch", str(entry)], check=True, capture_output=True,
                                text=True, timeout=15)
        if json.loads(result.stdout) != ["--prefix", str(prefix)]:
            raise RuntimeError("native Desktop Entry launch changed the program arguments")
    print("PASS: native Desktop Entry launch preserves quoted paths and literal field codes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="read-only validation (default)")
    mode.add_argument("--install", action="store_true", help="copy allowlisted files and create shortcut")
    parser.add_argument("--prefix", type=Path, default=runner.PREFIX,
                        help="existing private compatdata directory (default: runner.PREFIX)")
    parser.add_argument("--trust-shortcut", action="store_true",
                        help="mark the installed desktop entry trusted with gio")
    parser.add_argument("--self-check", action="store_true", help="check Desktop Entry quoting without Steam access")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if args.trust_shortcut and not args.install:
        parser.error("--trust-shortcut requires --install")
    prefix = checked_prefix(args.prefix)
    validate_payload()
    ddir = desktop_dir()
    entry = ddir / DESKTOP_NAME
    validate_desktop(entry)
    if args.install:
        copy_payload()
        install_shortcut(prefix, args.trust_shortcut)
        print(f"Installed project files in {MOD} and shortcut in {entry}")
    else:
        print(f"PASS: install destinations are safe; no changes made (mod: {MOD}, desktop: {entry})")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
