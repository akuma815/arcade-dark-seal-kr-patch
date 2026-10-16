"""DECO 74 타일 ROM 스크램블 해제 + deco16 8×8 타일 디코드 (Dark Seal 2 / Wizard Fire 문자 ROM용).

알고리즘 구조는 FBNeo deco16ic.cpp 의 deco_decrypt 를 따르고, 테이블은 common/config/deco74_tables.json 에서 읽는다.
- 입력은 FBNeo 적재 순서와 같은 바이트열: jb-04.10d 가 짝수 바이트, jb-05.12d 가 홀수 바이트 (0x20000 바이트)
- 16비트 워드는 빅엔디안으로 읽고 쓴다
- 8×8 타일: 타일당 16바이트(행마다 2바이트). 픽셀값 비트0·1 = 전반부 바이트 0·1, 비트2·3 = 후반부(len/2) 바이트 0·1, MSB 가 왼쪽 (deco16_tile_decode 규약)

사용:
  python common/scripts/deco74.py decrypt <romA(even)> <romB(odd)> <out.bin>
  python common/scripts/deco74.py render  <decrypted.bin> <out.png> [--scale N]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLES = json.loads((HERE.parent / "config" / "deco74_tables.json").read_text(encoding="utf-8"))
XOR_MASKS = TABLES["xor_masks"]
SWAP_PATTERNS = TABLES["swap_patterns"]
XOR_TABLE = TABLES["deco74_xor_table"]
ADDR_TABLE = TABLES["deco74_address_table"]
SWAP_TABLE = TABLES["deco74_swap_table"]


def bitswap16(val: int, order: list[int]) -> int:
    # order[0] 이 결과 비트 15, order[15] 가 결과 비트 0
    out = 0
    for k, src in enumerate(order):
        out |= ((val >> src) & 1) << (15 - k)
    return out


def inv_bitswap16(val: int, order: list[int]) -> int:
    out = 0
    for k, src in enumerate(order):
        out |= ((val >> (15 - k)) & 1) << src
    return out


def deco74_encrypt(plain: bytes) -> bytes:
    """deco74_decrypt 의 역함수. address_table 은 0x800 블록 내 전단사(검증됨).
    decrypt: out[i] = bitswap(buf[addr(i)] ^ xor[addr(i)&0x7ff], pat(i))  →  buf[addr(i)] = inv_bitswap(out[i], pat(i)) ^ xor[addr(i)&0x7ff]"""
    n = len(plain) // 2
    words = [int.from_bytes(plain[2 * i:2 * i + 2], "big") for i in range(n)]
    out = bytearray(len(plain))
    for i in range(n):
        addr = (i & ~0x7FF) | ADDR_TABLE[i & 0x7FF]
        pat = SWAP_TABLE[i & 0x7FF]
        v = inv_bitswap16(words[i], SWAP_PATTERNS[pat]) ^ XOR_MASKS[XOR_TABLE[addr & 0x7FF]]
        out[2 * addr:2 * addr + 2] = v.to_bytes(2, "big")
    return bytes(out)


def decode_tiles_16x16(data: bytes) -> list[list[list[int]]]:
    """deco16_tile_decode type 0: 타일당 절반마다 64바이트. 바이트 32~63 = 왼쪽 8px, 0~31 = 오른쪽 8px, 행 2바이트.
    픽셀값 비트0·1 = 전반부 바이트0·1, 비트2·3 = 후반부 바이트0·1."""
    half = len(data) // 2
    n = half // 64
    tiles = []
    for t in range(n):
        px = [[0] * 16 for _ in range(16)]
        for y in range(16):
            for hx, boff in ((0, 32), (8, 0)):
                b0 = data[t * 64 + boff + y * 2]
                b1 = data[t * 64 + boff + y * 2 + 1]
                b2 = data[half + t * 64 + boff + y * 2]
                b3 = data[half + t * 64 + boff + y * 2 + 1]
                for x in range(8):
                    s = 7 - x
                    px[y][hx + x] = ((b0 >> s) & 1) | (((b1 >> s) & 1) << 1) | (((b2 >> s) & 1) << 2) | (((b3 >> s) & 1) << 3)
        tiles.append(px)
    return tiles


def encode_tiles_16x16(tiles: list[list[list[int]]], out: bytearray) -> None:
    """tiles 를 평문 영역 out(길이 = 타일수*128) 에 기록한다 (decode_tiles_16x16 의 역함수)."""
    half = len(out) // 2
    for t, px in enumerate(tiles):
        for y in range(16):
            for hx, boff in ((0, 32), (8, 0)):
                b = [0, 0, 0, 0]
                for x in range(8):
                    v = px[y][hx + x]
                    for p in range(4):
                        b[p] |= ((v >> p) & 1) << (7 - x)
                out[t * 64 + boff + y * 2] = b[0]
                out[t * 64 + boff + y * 2 + 1] = b[1]
                out[half + t * 64 + boff + y * 2] = b[2]
                out[half + t * 64 + boff + y * 2 + 1] = b[3]


def interleave(even: bytes, odd: bytes) -> bytes:
    out = bytearray(len(even) + len(odd))
    out[0::2] = even
    out[1::2] = odd
    return bytes(out)


def deco74_decrypt(data: bytes) -> bytes:
    n = len(data) // 2
    words = [int.from_bytes(data[2 * i:2 * i + 2], "big") for i in range(n)]
    out = bytearray(len(data))
    for i in range(n):
        addr = (i & ~0x7FF) | ADDR_TABLE[i & 0x7FF]
        pat = SWAP_TABLE[i & 0x7FF]
        v = bitswap16(words[addr] ^ XOR_MASKS[XOR_TABLE[addr & 0x7FF]], SWAP_PATTERNS[pat])
        out[2 * i:2 * i + 2] = v.to_bytes(2, "big")
    return bytes(out)


def decode_tiles_8x8(data: bytes) -> list[list[list[int]]]:
    half = len(data) // 2
    n = (len(data) * 2) // 0x40
    tiles = []
    for t in range(n):
        px = [[0] * 8 for _ in range(8)]
        for y in range(8):
            # deco16_tile_decode: Plane = {half*8+8, half*8+0, 8, 0} → 비트3=후반부 바이트1, 비트2=후반부 바이트0, 비트1=전반부 바이트1, 비트0=전반부 바이트0
            b0 = data[t * 16 + y * 2]
            b1 = data[t * 16 + y * 2 + 1]
            b2 = data[half + t * 16 + y * 2]
            b3 = data[half + t * 16 + y * 2 + 1]
            for x in range(8):
                s = 7 - x
                px[y][x] = ((b0 >> s) & 1) | (((b1 >> s) & 1) << 1) | (((b2 >> s) & 1) << 2) | (((b3 >> s) & 1) << 3)
        tiles.append(px)
    return tiles


def encode_tiles_8x8(tiles: list[list[list[int]]], out: bytearray) -> None:
    """decode_tiles_8x8 의 역함수. out 길이 = 타일수*32 (전반부 = 비트0/1 평면, 후반부 = 비트2/3 평면)."""
    half = len(out) // 2
    for t, px in enumerate(tiles):
        for y in range(8):
            b0 = b1 = b2 = b3 = 0
            for x in range(8):
                v = px[y][x]
                s = 7 - x
                b0 |= (v & 1) << s
                b1 |= ((v >> 1) & 1) << s
                b2 |= ((v >> 2) & 1) << s
                b3 |= ((v >> 3) & 1) << s
            out[t * 16 + y * 2] = b0
            out[t * 16 + y * 2 + 1] = b1
            out[half + t * 16 + y * 2] = b2
            out[half + t * 16 + y * 2 + 1] = b3


def deinterleave(data: bytes) -> tuple[bytes, bytes]:
    return data[0::2], data[1::2]


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decrypt")
    d.add_argument("rom_even")
    d.add_argument("rom_odd")
    d.add_argument("out")
    r = sub.add_parser("render")
    r.add_argument("decrypted")
    r.add_argument("out")
    r.add_argument("--scale", type=int, default=2)
    r.add_argument("--cols", type=int, default=64)
    a = ap.parse_args()
    if a.cmd == "decrypt":
        data = interleave(Path(a.rom_even).read_bytes(), Path(a.rom_odd).read_bytes())
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_bytes(deco74_decrypt(data))
        print(f"decrypted {len(data)} bytes -> {a.out}")
    else:
        from render_chars import render
        tiles = decode_tiles_8x8(Path(a.decrypted).read_bytes())
        img, nonblank = render(tiles, a.cols, a.scale)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        img.save(a.out)
        print(f"tiles={len(tiles)} nonblank={nonblank} -> {a.out}")


if __name__ == "__main__":
    main()
