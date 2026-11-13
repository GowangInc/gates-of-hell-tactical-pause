#!/usr/bin/env python3
"""Verify the installed GoH client and enable this mod for that exact build."""

import argparse
import hashlib
from pathlib import Path

import verify_build

MOD_ID = "tactical_pause"
MARKER = "enable-tactical-pause"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client",
        type=Path,
        metavar="PATH",
        help="explicit path to call_to_arms.exe when Steam library discovery fails",
    )
    args = parser.parse_args()
    client = args.client or verify_build.locate_client()
    if client is None:
        print("REFUSED: GoH client not found; pass --client PATH to call_to_arms.exe.")
        return 1
    try:
        digest = hashlib.sha256(client.read_bytes()).hexdigest()
    except OSError as error:
        print(f"REFUSED: cannot read GoH client {client}: {error}")
        return 1
    if digest != verify_build.EXPECTED_SHA256:
        print(f"REFUSED: unsupported GoH client SHA-256: {digest}; expected {verify_build.EXPECTED_SHA256}")
        return 1

    game_root = client.parent.parent.parent
    mod_dir = game_root / "gohse" / "mods" / MOD_ID
    if not game_root.is_dir() or not (game_root / "binaries" / "x64").is_dir():
        print(f"REFUSED: cannot locate the game root beside {client}; install the game and try again.")
        return 1
    if not mod_dir.is_dir():
        print(f"REFUSED: mod folder not found: {mod_dir}. Extract this mod to that folder first.")
        return 1
    marker = mod_dir / MARKER
    try:
        marker.write_text(verify_build.EXPECTED_SHA256 + "\n", encoding="ascii")
    except OSError as error:
        print(f"REFUSED: cannot write activation marker {marker}: {error}")
        return 1
    print(f"Enabled for verified build at {mod_dir}. Start the game via Steam; Linux/Proton users must set WINEDLLOVERRIDES=version=n,b %command% in Steam launch options.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
