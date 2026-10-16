"""Dark Seal 1 PoC 빌드: 프롤로그 첫 문장을 가로쓰기 한글로 바꿔 FBNeo IPS 로 띄운다.

절차
 1. original→extracted ROM 로드, 디코드/인코드 무변경 왕복 바이트 동일 검사 (실패 시 중단)
 2. 한글 글리프(Galmuri11_16x16, 본체 7 + 외곽선 2)를 미참조 타일 뱅크 0xa00~ 에 4타일 단위로 기록
 3. 프롤로그 스크립트(0x7ba18)를 가로쓰기 워드 열로 교체, 후리가나 쌍 블록(0x7bc0c)을 0xffff 로 무효화
 4. 변경 범위가 선언 범위 안인지 검사(Expected Write)
 5. build/poc/ 에 ROM·IPS·dat, FBNeo support/ips/darksealj/ 에 복사

사용: python darksealj/workspace/scripts/build_poc.py [--no-install]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zlib
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds1lib as L  # noqa: E402

FONT16 = L.ROOT.parent.parent / "Font" / "Galmuri11_16x16.png"
BUILD = L.GAME / "build" / "poc"
FBNEO_IPS = Path(r"H:\FBNeo v1.0.0.03\support\ips\darksealj")
POC_NAME = "poc"
GLYPH_BANK_START = 0xA00        # 스크립트 미참조 구간 (survey §3). PoC 전용 — 소비자 미확인
GLYPH_BANK_END = 0x1000

# PoC 초벌 문구 (프롤로그 전문, 사람 검토 전). 한 줄 ≤ 14셀, 전체 ≤ 14줄(빈 줄 포함) — 원장 확정 후 extract/translation 으로 대체
POC_LINES = [
    "백성의 마음에 검은 그림자",
    "가득하고, 아득한 땅 밑의",
    "문이 열리던 때, 그 암흑",
    "속에서 나온 마의 무리가",
    "세상을 사악한 어둠으로",
    "덮으려 하니,",
    "",
    "그때, 숙명으로 모인",
    "용사들이 빛의 힘과 기예로",
    "이를 봉인하리라.",
    "그리하여 다시 세상에",
    "빛이 가득하리라.",
    "",
    "(에트루리아 전승에서)",
]

PUNCT = {
    ",": ["................", "................", "................", "................", "................", "................",
          "................", "................", "................", "................", "................", "....##..........",
          "....##..........", ".....#..........", "....#...........", "................"],
    ".": ["................", "................", "................", "................", "................", "................",
          "................", "................", "................", "................", "................", "....##..........",
          "....##..........", "................", "................", "................"],
    "(": ["................", "................", ".......#........", "......#.........", ".....#..........", ".....#..........",
          ".....#..........", ".....#..........", ".....#..........", ".....#..........", ".....#..........", "......#.........",
          ".......#........", "................", "................", "................"],
    ")": ["................", "................", "....#...........", ".....#..........", "......#.........", "......#.........",
          "......#.........", "......#.........", "......#.........", "......#.........", "......#.........", ".....#..........",
          "....#...........", "................", "................", "................"],
}


def ips_build(orig: bytes, new: bytes) -> bytes:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-install", action="store_true")
    ap.add_argument("--step-mask", type=lambda v: int(v, 0), default=3, help="(countdown & mask)==0 인 프레임마다 Y+1 (3=4프레임마다)")
    ap.add_argument("--y-stop", type=lambda v: int(v, 0), default=None, help="텍스트 Y 스크롤 정지값 (기본 224: 첫 줄이 화면 상단 16px 에 닿는 값)")
    ap.add_argument("--start-row", type=int, default=30, help="스크립트 시작 타일맵 행 (8px 단위, 30=화면 아래 가장자리)")
    a = ap.parse_args()

    prg_files, chr_region = L.load_originals()

    # 1. 무변경 왕복
    img = L.prg_decode(prg_files)
    assert L.prg_encode(img) == prg_files, "프로그램 ROM 왕복 실패"
    tiles = L.chr_decode(chr_region)
    assert L.chr_encode(tiles) == chr_region, "문자 ROM 왕복 실패"
    print("[OK] 무변경 왕복: 프로그램 4파일, 문자 ROM 2파일 바이트 동일")

    # 2. 글리프 배정·기록
    sheet = Image.open(FONT16).convert("RGBA")
    chars = sorted({c for line in POC_LINES for c in line if c != " "})
    glyph_base: dict[str, int] = {}
    nxt = GLYPH_BANK_START
    for c in chars:
        if nxt + 4 > GLYPH_BANK_END:
            raise SystemExit("글리프 뱅크 부족")
        if c in PUNCT:
            mask = [[1 if ch == "#" else 0 for ch in row] for row in PUNCT[c]]
        else:
            m11 = L.hangul_sheet_glyph(sheet, c, 16)
            mask = [[0] * 16 for _ in range(16)]
            for y in range(11):          # 11×11 글리프를 (2,2) 로 이동
                for x in range(11):
                    mask[y + 2][x + 2] = m11[y][x]
        L.glyph_to_16x16(tiles, nxt, L.mask_to_glyph(mask))
        glyph_base[c] = nxt
        nxt += 4
    print(f"[OK] 글리프 {len(chars)}자 → 타일 {GLYPH_BANK_START:03x}~{nxt - 1:03x}")

    # 3. 스크립트
    words: list[int] = []
    for line in POC_LINES:
        if line:
            words.append(0x0000)   # 왼쪽 여백 1셀
            for c in line:
                if len(line) > 14:
                    raise SystemExit(f"줄이 14셀 초과: {line}")
                words.append(0x0000 if c == " " else glyph_base[c])
        words.append(0xFFFE)
    new_script = L.script_emit(words)
    orig_script, orig_end = L.script_parse(img, L.SCRIPT_PROLOGUE)
    orig_len = orig_end - L.SCRIPT_PROLOGUE
    if len(new_script) > orig_len:
        raise SystemExit(f"스크립트 길이 초과 {len(new_script)} > {orig_len}")
    new_img = bytearray(img)
    new_img[L.SCRIPT_PROLOGUE:L.SCRIPT_PROLOGUE + len(new_script)] = new_script
    new_img[L.FURIGANA_PAIRS:L.FURIGANA_PAIRS + 2] = b"\xff\xff"
    print(f"[OK] 스크립트 {len(new_script)}/{orig_len} 바이트, 후리가나 블록 무효화")

    # 3b. 세로 크롤: 텍스트 레이어 스크롤 루틴(0xffac) 치환, X 초기값 0x100→0, 스크립트 시작 행을 화면 아래(30행)로
    s, e = L.PROLOGUE_TEXT_SCROLL_ROUTINE
    # 정지 위치: 월드판처럼 본문이 다 올라와 첫 줄이 화면 상단(여백 TOP_MARGIN)에 닿으면 멈춘다.
    # 블록은 시작 행 30(y=240) 부터 16px × 줄 수. 스크롤 Y 만큼 위로 이동하므로 첫 줄 y = 240 - Y.
    TOP_MARGIN = 16
    text_rows = words.count(0xFFFE)                     # 줄바꿈 수 = 16px 행 수 (마지막 줄 포함)
    text_h = text_rows * 16
    if text_h > 240 - TOP_MARGIN:
        raise SystemExit(f"본문 {text_rows}줄({text_h}px) 이 화면(240-{TOP_MARGIN}px)을 넘는다 — 14줄 이하로")
    y_stop = a.y_stop if a.y_stop is not None else 240 - TOP_MARGIN
    new_img[s:e] = L.prologue_vertical_scroll_code(step_mask=a.step_mask, y_stop=y_stop)
    new_img[L.PROLOGUE_TEXT_X_INIT_IMM:L.PROLOGUE_TEXT_X_INIT_IMM + 2] = b"\x00\x00"
    a2 = L.TEXT_RAM + a.start_row * 128
    new_img[L.PROLOGUE_A2_IMM:L.PROLOGUE_A2_IMM + 4] = a2.to_bytes(4, "big")
    print(f"[OK] 세로 크롤: 텍스트 Y+1 every {a.step_mask + 1} frames, {text_rows}줄({text_h}px) → 정지 Y={y_stop} (첫 줄 y={240 - y_stop}), X init 0, 시작 행 {a.start_row} (a2={a2:#x})")

    # 4. Expected Write
    allowed_prg = [(L.SCRIPT_PROLOGUE, L.SCRIPT_PROLOGUE + orig_len), (L.FURIGANA_PAIRS, L.FURIGANA_PAIRS + 2),
                   (s, e), (L.PROLOGUE_TEXT_X_INIT_IMM, L.PROLOGUE_TEXT_X_INIT_IMM + 2), (L.PROLOGUE_A2_IMM, L.PROLOGUE_A2_IMM + 4)]
    for s, e in changed_ranges(img, bytes(new_img)):
        if not any(a0 <= s and e <= a1 for a0, a1 in allowed_prg):
            raise SystemExit(f"허용 범위 밖 프로그램 변경 {s:06x}-{e:06x}")
    new_chr = L.chr_encode(tiles)
    allowed_chr = [(off + GLYPH_BANK_START * 8, off + nxt * 8) for off in L.PLANE_OFFS]
    for s, e in changed_ranges(chr_region, new_chr):
        if not any(a0 <= s and e <= a1 for a0, a1 in allowed_chr):
            raise SystemExit(f"허용 범위 밖 문자 ROM 변경 {s:06x}-{e:06x}")
    print("[OK] Expected Write: 선언 범위 밖 변경 0바이트")

    # 5. 출력
    BUILD.mkdir(parents=True, exist_ok=True)
    new_prg_files = L.prg_encode(bytes(new_img))
    new_chr_files = L.chr_split(new_chr)
    orig_all = {**prg_files, **L.chr_split(chr_region)}
    new_all = {**new_prg_files, **new_chr_files}
    dat_lines = []
    report = {"glyph_base": {c: f"{b:03x}" for c, b in glyph_base.items()}, "roms": {}}
    for name, data in new_all.items():
        (BUILD / name).write_bytes(data)
        if data != orig_all[name]:
            ips_name = f"{POC_NAME}-{name.replace('.', '_')}"
            (BUILD / f"{ips_name}.ips").write_bytes(ips_build(orig_all[name], data))
            dat_lines.append(f"{name}\t{ips_name}\tCRC({zlib.crc32(orig_all[name]) & 0xFFFFFFFF:08x})")
            report["roms"][name] = {"changed_bytes": sum(1 for x, y in zip(orig_all[name], data) if x != y), "ips": ips_name + ".ips"}
    dat = "\n".join(dat_lines) + "\n\n[en_US]\nDark Seal Korean PoC\n\n[ko_KR]\n다크씰 한글 PoC\n"
    (BUILD / f"{POC_NAME}.dat").write_text(dat, encoding="utf-8")
    (BUILD / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OK] build:", ", ".join(report["roms"]))
    if not a.no_install:
        FBNEO_IPS.mkdir(parents=True, exist_ok=True)
        for f in [BUILD / f"{POC_NAME}.dat"] + list(BUILD.glob(f"{POC_NAME}-*.ips")):
            shutil.copy(f, FBNEO_IPS / f.name)
        print("[OK] FBNeo support/ips/darksealj/ 에 설치:", POC_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
