"""IPS 생성·변경 범위 검사 공용 유틸 (두 게임 공용)."""
from __future__ import annotations

import zlib


def ips_build(orig: bytes, new: bytes) -> bytes:
    """원본 대비 차이를 IPS 레코드로. 레코드는 0xffff 바이트 이하, 1바이트 간격의 차이는 한 레코드로 합친다."""
    assert len(orig) == len(new)
    out = bytearray(b"PATCH")
    i = 0
    while i < len(orig):
        if orig[i] == new[i]:
            i += 1
            continue
        j = i
        while j < len(orig) and (orig[j] != new[j] or (j + 1 < len(orig) and orig[j + 1] != new[j + 1])) and j - i < 0xFFFF:
            j += 1
        chunk = new[i:j]
        out += i.to_bytes(3, "big") + len(chunk).to_bytes(2, "big") + chunk
        i = j
    out += b"EOF"
    return bytes(out)


def ips_apply(orig: bytes, ips: bytes) -> bytes:
    assert ips[:5] == b"PATCH" and ips[-3:] == b"EOF"
    out = bytearray(orig)
    p = 5
    while p < len(ips) - 3:
        off = int.from_bytes(ips[p:p + 3], "big")
        size = int.from_bytes(ips[p + 3:p + 5], "big")
        p += 5
        if size == 0:  # RLE
            rle = int.from_bytes(ips[p:p + 2], "big")
            out[off:off + rle] = bytes([ips[p + 2]]) * rle
            p += 3
        else:
            out[off:off + size] = ips[p:p + size]
            p += size
    return bytes(out)


def changed_ranges(orig: bytes, new: bytes) -> list[tuple[int, int]]:
    rs = []
    i = 0
    while i < len(orig):
        if orig[i] != new[i]:
            j = i
            while j < len(orig) and orig[j] != new[j]:
                j += 1
            rs.append((i, j))
            i = j
        else:
            i += 1
    return rs


def check_allowed(orig: bytes, new: bytes, allowed: list[tuple[int, int]], label: str) -> int:
    """선언 범위 밖 변경이 있으면 SystemExit. 변경 바이트 수를 돌려준다."""
    # 인접·중복 허용 범위를 합친다 (연속 셀/타일 변경이 한 런으로 잡히므로)
    merged: list[tuple[int, int]] = []
    for a0, a1 in sorted(allowed):
        if merged and a0 <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], a1))
        else:
            merged.append((a0, a1))
    allowed = merged
    n = 0
    for s, e in changed_ranges(orig, new):
        if not any(a0 <= s and e <= a1 for a0, a1 in allowed):
            raise SystemExit(f"[{label}] 허용 범위 밖 변경 {s:06x}-{e:06x}")
        n += e - s
    return n


def crc32(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"
