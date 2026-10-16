"""문자 ROM 을 8×8 4bpp 타일 격자 PNG 로 렌더한다. 레이아웃은 가설별로 선택한다.

--layout planar4  : ROM A+B 를 이어 붙인 영역을 4등분해 각 1/4 이 1비트 평면 (타일 1개 = 평면당 8바이트)
                    ex) Dark Seal: fz_02.j1 → 평면 0·1, fz_03.j2 → 평면 2·3, 각 32KB, 4096타일
--layout rowpair  : ROM 마다 타일 1개 = 16바이트 (행마다 2바이트 = 평면 2개) — 첫 시도. Dark Seal 에서는 틀린 것으로 판명
비트 순서는 MSB 가 왼쪽 픽셀. 결과 PNG 를 눈으로 확인한다.

사용: python common/scripts/render_chars.py <romA> <romB> <out.png> [--layout planar4|rowpair] [--scale N]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

PALETTE = [(0, 0, 0), (40, 40, 120), (80, 80, 200), (120, 120, 255), (60, 120, 60), (90, 180, 90), (130, 230, 130), (170, 255, 170),
           (120, 60, 60), (180, 90, 90), (230, 130, 130), (255, 170, 170), (150, 150, 150), (190, 190, 190), (225, 225, 225), (255, 255, 255)]


def decode_rowpair(rom_a: bytes, rom_b: bytes) -> list[list[list[int]]]:
    n = min(len(rom_a), len(rom_b)) // 16
    tiles = []
    for t in range(n):
        px = [[0] * 8 for _ in range(8)]
        for y in range(8):
            a0, a1 = rom_a[t * 16 + y * 2], rom_a[t * 16 + y * 2 + 1]
            b0, b1 = rom_b[t * 16 + y * 2], rom_b[t * 16 + y * 2 + 1]
            for x in range(8):
                bit = 7 - x
                px[y][x] = ((a0 >> bit) & 1) | (((a1 >> bit) & 1) << 1) | (((b0 >> bit) & 1) << 2) | (((b1 >> bit) & 1) << 3)
        tiles.append(px)
    return tiles


def decode_planar4(region: bytes, plane_offsets: tuple[int, int, int, int] | None = None) -> list[list[list[int]]]:
    """plane_offsets[i] = 평면 i 의 시작 오프셋. 평면 0 이 MSB(비트3) — FBNeo/MAME GfxDecode 규약과 같다.
    기본값은 영역 4등분 순서. Dark Seal 은 (0x00000, 0x10000, 0x08000, 0x18000)."""
    q = len(region) // 4
    offs = plane_offsets or (0, q, 2 * q, 3 * q)
    n = q // 8
    tiles = []
    for t in range(n):
        px = [[0] * 8 for _ in range(8)]
        for y in range(8):
            rows = [region[offs[p] + t * 8 + y] for p in range(4)]
            for x in range(8):
                bit = 7 - x
                px[y][x] = sum(((rows[p] >> bit) & 1) << (3 - p) for p in range(4))
        tiles.append(px)
    return tiles


def render(tiles, cols: int, scale: int) -> tuple[Image.Image, int]:
    rows = (len(tiles) + cols - 1) // cols
    img = Image.new("RGB", (cols * 8, rows * 8), (0, 0, 0))
    nonblank = 0
    for i, t in enumerate(tiles):
        ox, oy = (i % cols) * 8, (i // cols) * 8
        blank = True
        for y in range(8):
            for x in range(8):
                v = t[y][x]
                if v:
                    blank = False
                    img.putpixel((ox + x, oy + y), PALETTE[v])
        nonblank += 0 if blank else 1
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    return img, nonblank


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom_a")
    ap.add_argument("rom_b")
    ap.add_argument("out")
    ap.add_argument("--layout", choices=["planar4", "rowpair"], default="planar4")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--cols", type=int, default=64)
    a = ap.parse_args()
    ra, rb = Path(a.rom_a).read_bytes(), Path(a.rom_b).read_bytes()
    tiles = decode_planar4(ra + rb) if a.layout == "planar4" else decode_rowpair(ra, rb)
    img, nonblank = render(tiles, a.cols, a.scale)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    img.save(a.out)
    print(f"layout={a.layout} tiles={len(tiles)} nonblank={nonblank} grid={a.cols}x{(len(tiles)+a.cols-1)//a.cols} -> {a.out}")


if __name__ == "__main__":
    main()
