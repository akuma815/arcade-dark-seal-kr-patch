"""글리프(16×16 타일 base)↔문자 전사표 도구.

- seed  : 전사 확정 텍스트(workspace/text/source/transcriptions.json)의 각 블록을 글리프 열과 정렬해 표를 만든다.
          글리프 수와 문자 수가 다르면 그 블록은 건너뛰고 보고한다. 같은 base 에 다른 문자가 붙으면 충돌로 보고한다.
- sheet : 아직 전사되지 않은 글리프를 라벨(hex) 붙여 PNG 시트로 그린다 (사람/모델이 읽고 표에 추가).
- decode: 표로 모든 A 스크립트를 문자열로 복원해 source/ds1_text_ja.json 에 쓴다 (미전사 글리프는 〔xxx〕).
표 파일: workspace/font/mapping/ds1_glyph_map.json  { "2b4": "民", ... }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds1lib as L  # noqa: E402

SRC = L.GAME / "workspace" / "text" / "source"
MAP = L.GAME / "workspace" / "font" / "mapping" / "ds1_glyph_map.json"
BLOCKS = SRC / "ds1_blocks.json"
TRANS = SRC / "transcriptions.json"


def load_map() -> dict[str, str]:
    return json.loads(MAP.read_text(encoding="utf-8")) if MAP.exists() else {}


def save_map(m: dict[str, str]) -> None:
    MAP.parent.mkdir(parents=True, exist_ok=True)
    MAP.write_text(json.dumps(dict(sorted(m.items())), ensure_ascii=False, indent=1), encoding="utf-8")


def all_scripts(blocks: dict) -> list[dict]:
    out = []
    for b in blocks["blocks"]:
        for r in (b.get("entries") or [b]):
            if r["type"] == "A":
                out.append(r)
    return out


def script_glyphs(rec: dict) -> list[int]:
    return [int(h, 16) & 0xFFF for row in rec["rows"] for h in row if int(h, 16) not in (0, 0xFFFE)]


def cmd_seed(a) -> None:
    blocks = json.loads(BLOCKS.read_text(encoding="utf-8"))
    trans = json.loads(TRANS.read_text(encoding="utf-8"))
    m = load_map()
    conflicts = []
    by_id = {r["id"]: r for r in all_scripts(blocks)}
    for sid, text in trans.items():
        rec = by_id.get(sid)
        if rec is None:
            print(f"  [skip] {sid}: 블록 없음")
            continue
        chars = [c for c in text if c not in " \n　"]
        glyphs = script_glyphs(rec)
        if len(chars) != len(glyphs):
            print(f"  [mismatch] {sid} ({rec['label']}): glyphs={len(glyphs)} chars={len(chars)} — 전사 확인 필요")
            continue
        for g, c in zip(glyphs, chars):
            k = f"{g:03x}"
            if k in m and m[k] != c:
                conflicts.append((k, m[k], c, sid))
            else:
                m[k] = c
        print(f"  [ok] {sid} ({rec['label']}): {len(glyphs)} glyphs aligned")
    save_map(m)
    print(f"[OK] map entries={len(m)} conflicts={len(conflicts)}")
    for k, old, new, sid in conflicts:
        print(f"  conflict {k}: '{old}' vs '{new}' in {sid}")


def cmd_sheet(a) -> None:
    blocks = json.loads(BLOCKS.read_text(encoding="utf-8"))
    m = load_map()
    used = sorted(int(k, 16) for k in blocks["glyph_usage"])
    todo = [g for g in used if f"{g:03x}" not in m] if not a.all else used
    _, chr_region = L.load_originals()
    tiles = L.chr_decode(chr_region)
    S, cols = a.scale, a.cols
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = None
    cell_w, cell_h = 16 * S + 12, 16 * S + 26
    per_sheet = cols * a.rows
    out_dir = L.GAME / "work" / "glyph_sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    order_lines = []
    for si in range(0, len(todo), per_sheet):
        chunk = todo[si:si + per_sheet]
        rows = (len(chunk) + cols - 1) // cols
        img = Image.new("RGB", (cols * cell_w + 40, rows * cell_h), (24, 24, 24))
        dr = ImageDraw.Draw(img)
        for i, g in enumerate(chunk):
            px = L.glyph_from_16x16(tiles, g)
            ox, oy = 40 + (i % cols) * cell_w + 6, (i // cols) * cell_h + 2
            for y in range(16):
                for x in range(16):
                    v = px[y][x]
                    if v:
                        col = (255, 255, 255) if v == 7 else (255, 90, 90) if v == 2 else (120, 200, 255)
                        dr.rectangle((ox + x * S, oy + y * S, ox + x * S + S - 1, oy + y * S + S - 1), fill=col)
            dr.text((ox, oy + 16 * S + 2), f"{g:03x}", fill=(255, 255, 0), font=font)
        for r in range(rows):
            dr.text((2, r * cell_h + 16 * S // 2), f"r{r + 1}", fill=(0, 255, 255), font=font)
        p = out_dir / f"glyphs_{si // per_sheet + 1:02d}.png"
        img.save(p)
        sheet_no = si // per_sheet + 1
        for r in range(rows):
            codes = chunk[r * cols:(r + 1) * cols]
            order_lines.append(f"S{sheet_no:02d} r{r + 1}: " + " ".join(f"{g:03x}" for g in codes))
        print(f"  {p.name}: {len(chunk)} glyphs ({chunk[0]:03x}..{chunk[-1]:03x})")
    (out_dir / "order.txt").write_text("\n".join(order_lines) + "\n", encoding="utf-8")
    print("\n".join(order_lines))
    print(f"[OK] todo={len(todo)} of used={len(used)}")


def cmd_decode(a) -> None:
    blocks = json.loads(BLOCKS.read_text(encoding="utf-8"))
    m = load_map()
    out = {}
    missing = set()
    for rec in all_scripts(blocks):
        lines = []
        for row in rec["rows"]:
            s = ""
            for h in row:
                w = int(h, 16)
                if w == 0:
                    s += "　"
                elif (w & 0xFFF) < 0x80:          # 1타일 ASCII (계급명 등: 타일 = ASCII 코드)
                    s += chr(w & 0x7F)
                else:
                    k = f"{w & 0xFFF:03x}"
                    if k in m:
                        s += m[k]
                    else:
                        s += f"〔{k}〕"
                        missing.add(k)
            lines.append(s.rstrip("　"))
        out[rec["id"]] = {"label": rec["label"], "lines": lines}
    p = SRC / "ds1_text_ja.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {p.name}: scripts={len(out)} unmapped glyphs={len(missing)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    s = sub.add_parser("sheet")
    s.add_argument("--all", action="store_true")
    s.add_argument("--cols", type=int, default=8)
    s.add_argument("--rows", type=int, default=6)
    s.add_argument("--scale", type=int, default=4)
    sub.add_parser("decode")
    f = sub.add_parser("fill", help="행 단위 전사 문자열(JSON: {'S01 r1': '川幸彦…'})을 order.txt 와 zip 해 표에 추가")
    f.add_argument("json_path")
    a = ap.parse_args()
    {"seed": cmd_seed, "sheet": cmd_sheet, "decode": cmd_decode, "fill": cmd_fill}[a.cmd](a)


def cmd_fill(a) -> None:
    order = {}
    for line in (L.GAME / "work" / "glyph_sheets" / "order.txt").read_text(encoding="utf-8").splitlines():
        key, codes = line.split(":", 1)
        order[key.strip()] = [int(c, 16) for c in codes.split()]
    rows = json.loads(Path(a.json_path).read_text(encoding="utf-8"))
    m = load_map()
    added = 0
    for key, text in rows.items():
        codes = order.get(key)
        chars = [c for c in text if c not in " \n"]
        if codes is None:
            print(f"  [skip] {key}: order.txt 에 없음")
            continue
        if len(chars) != len(codes):
            print(f"  [mismatch] {key}: codes={len(codes)} chars={len(chars)} → 건너뜀: {text}")
            continue
        for g, c in zip(codes, chars):
            k = f"{g:03x}"
            if k in m and m[k] != c:
                print(f"  conflict {k}: '{m[k]}' vs '{c}'")
            m[k] = c
            added += 1
    save_map(m)
    print(f"[OK] filled {added}, map entries={len(m)}")


if __name__ == "__main__":
    main()
