#!/usr/bin/env python3
"""Read-only verification of the exact GoH client used for native research."""

import hashlib
import struct
import sys
from pathlib import Path

DEFAULT_EXE = (
    Path.home() / ".steam/debian-installation/steamapps/common"
    / "Call to Arms - Gates of Hell/binaries/x64/call_to_arms.exe"
)
EXPECTED_SHA256 = "4b6a807ad867c4f6eb1019376224d74fa3a6ac048355739ab0b76d73c7c0a267"
TARGETS = {
    0x25C980: "48 89 5c 24 08 55 48 8d 6c 24 a9 48 81 ec c0 00",
    0x269130: "48 83 3d 08 dd 2e 01 00 0f 95 c0 c3",
    0x269170: "48 8b d1 48 8d 0d 86 dc 2e 01 e9 31 5c 3f 00",
    0x269190: "48 8b d1 48 8d 0d 66 dc 2e 01 e9 a1 5d 3f 00",
    0x65EDB0: "48 89 5c 24 18 41 56 48 81 ec 80 00 00 00 48 8b 41 38",
    0x65EF40: "40 53 48 83 ec 60 48 8b 41 38 48 8b d9 4c 8b c8",
    0x6532B0: "40 53 48 83 ec 20 48 8b d9 48 89 51 18 e8 fe 06",
    0x6540E0: "48 89 74 24 20 41 56 48 83 ec 20 4c 8b f2 48 8b",
    0xC65C20: "40 53 48 83 ec 30 e8 05 ff ff ff 48 8b 58 50",
    0xC6B190: "48 89 5c 24 18 57 48 83 ec 50 0f b6 da 48 8b f9",
    0xC6BCE0: "48 89 5c 24 10 57 48 83 ec 50 0f b6 41 21 48 8b f9",
    0xC73030: "40 55 53 56 57 41 55 41 56 41 57 48 8d 6c 24 d9",
    0xC73BB0: "40 53 48 83 ec 40 80 b9 43 02 00 00 00 48 8b d9",
    0xC75CF0: "40 53 48 83 ec 60 48 8b d9 84 d2 74 0b 83 b9 44 02",
    0x7EFA10: "48 89 5c 24 18 57 48 81 ec a0 00 00 00 48 8b f9",
    0xC73C42: "e8 69 b1 9e ff",
    0xC73C64: "e8 d7 b2 9e ff",
    0x2DF1C0: "48 89 5c 24 10 48 89 74 24 18 55 48 8d 6c 24 a9",
    0x2DF480: "48 89 5c 24 10 56 48 81 ec b0 00 00 00 8b da 48 8b f1",
    0xC725E0: "40 57 48 83 ec 50 48 89 74 24 68 48 8b f9 8b f2",
}


def rva_offsets(data: bytes) -> dict[int, int]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise ValueError("not a PE executable")
    section_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    section_table = pe + 24 + optional_size
    offsets = {}
    for index in range(section_count):
        offset = section_table + index * 40
        rva = struct.unpack_from("<I", data, offset + 12)[0]
        raw_size, raw_offset = struct.unpack_from("<II", data, offset + 16)
        for target in TARGETS:
            if rva <= target < rva + raw_size:
                offsets[target] = raw_offset + target - rva
    return offsets


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXE
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        print(f"FAIL: unsupported SHA-256 for {path.name}: {digest}")
        return 1
    offsets = rva_offsets(data)
    failures = []
    for rva, expected_hex in TARGETS.items():
        expected = bytes.fromhex(expected_hex)
        offset = offsets.get(rva)
        if offset is None or data[offset : offset + len(expected)] != expected:
            failures.append(rva)
    if failures:
        print("FAIL: target bytes mismatch: " + ", ".join(f"0x{r:x}" for r in failures))
        return 1
    print(f"PASS: {path.name} SHA-256 and {len(TARGETS)} native targets match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
