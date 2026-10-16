"""Dark Seal 1 텍스트 추출기 — 프로그램 ROM 의 텍스트 블록을 JSON 원장(source)으로 덤프한다.

형식 (docs/survey.md §4):
  A  글리프 스크립트: 워드 열. pal<<12|k(16×16 글리프), 0=빈 셀, 0xfffe=줄바꿈, 0xffff=끝
  B  좌표·타일 쌍: [타일맵 바이트 오프셋][워드] … 0xffff
  C  ASCII 문자열: [오프셋 워드][ASCII…][00 패딩][0xfe] … 0xffff (타일 = ASCII 코드, 상위 비트는 d6)
안정 ID = "<형식>:<블록 주소>" , 행/셀 인덱스는 레코드 안에.
출력: workspace/text/source/ds1_blocks.json  (+ 글리프 사용 통계)
사용: python darksealj/workspace/scripts/extract_text.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds1lib as L  # noqa: E402

OUT = L.GAME / "workspace" / "text" / "source" / "ds1_blocks.json"

# (주소, 형식, 라벨, 포인터 수) — survey §5
BLOCKS = [
    (0x7BA18, "A", "prologue", 0),
    (0x7BC0C, "B", "prologue_furigana", 0),
    (0x7BC62, "A", "title_line", 0),
    (0x7BC8A, "C", "profile_labels", 0),
    (0x7BD00, "C", "profile_values", 4),
    (0x7BF00, "A", "story", 4),
    (0x7C204, "A", "briefing", 8),
    (0x7C4C4, "A", "king_message", 8),
    (0x7C670, "A", "villain", 7),
    (0x7CA0C, "A", "ending", 0),
    (0x7CA80, "A", "staff_roll", 11),
    (0x7CD8E, "C", "credits_en", 0),
    (0x7E03E, "A", "rank_names", 0),
]


def parse_A(img: bytes, off: int) -> dict:
    words, end = L.script_parse(img, off)
    rows: list[list[int]] = [[]]
    for w in words:
        if w == 0xFFFE:
            rows.append([])
        else:
            rows[-1].append(w)
    glyphs = [w & 0xFFF for w in words if w not in (0, 0xFFFE)]
    return {"type": "A", "addr": f"{off:06x}", "end": f"{end:06x}", "size": end - off, "rows": [[f"{w:04x}" for w in r] for r in rows],
            "glyph_count": len(glyphs), "palettes": sorted({w >> 12 for w in words if w not in (0, 0xFFFE)})}


def parse_B(img: bytes, off: int) -> dict:
    pairs = []
    o = off
    while True:
        a = int.from_bytes(img[o:o + 2], "big")
        if a == 0xFFFF:
            o += 2
            break
        v = int.from_bytes(img[o + 2:o + 4], "big")
        pairs.append({"tilemap_byte_off": f"{a:04x}", "col": (a // 2) % 64, "row": (a // 2) // 64, "word": f"{v:04x}"})
        o += 4
    return {"type": "B", "addr": f"{off:06x}", "end": f"{o:06x}", "size": o - off, "pairs": pairs}


def parse_C(img: bytes, off: int) -> dict:
    items = []
    o = off
    while True:
        pos = int.from_bytes(img[o:o + 2], "big")
        if pos == 0xFFFF:
            o += 2
            break
        o += 2
        s = o
        while img[o] != 0xFE:
            o += 1
        raw = img[s:o]
        o += 1
        text = raw.rstrip(b"\x00").decode("latin1")
        items.append({"tilemap_byte_off": f"{pos:04x}", "col": (pos // 2) % 64, "row": (pos // 2) // 64, "text": text,
                      "raw_hex": raw.hex(), "max_len": len(raw)})
    return {"type": "C", "addr": f"{off:06x}", "end": f"{o:06x}", "size": o - off, "items": items}


PARSERS = {"A": parse_A, "B": parse_B, "C": parse_C}


def main() -> int:
    prg_files, _ = L.load_originals()
    img = L.prg_decode(prg_files)
    out = {"source": "darksealj program ROM (decoded)", "blocks": []}
    glyph_use: Counter = Counter()
    for addr, kind, label, nptr in BLOCKS:
        if nptr:
            targets = []
            for i in range(nptr):
                targets.append(int.from_bytes(img[addr + i * 4:addr + i * 4 + 4], "big"))
            entries = []
            for i, t in enumerate(targets):
                rec = PARSERS[kind](img, t)
                rec["id"] = f"{kind}:{t:06x}"
                rec["label"] = f"{label}[{i}]"
                entries.append(rec)
            out["blocks"].append({"id": f"T:{addr:06x}", "label": label, "type": "table", "entries": entries,
                                  "pointers": [f"{t:06x}" for t in targets]})
            recs = entries
        else:
            rec = PARSERS[kind](img, addr)
            rec["id"] = f"{kind}:{addr:06x}"
            rec["label"] = label
            out["blocks"].append(rec)
            recs = [rec]
        for r in recs:
            if r["type"] == "A":
                for row in r["rows"]:
                    for h in row:
                        w = int(h, 16)
                        if w not in (0, 0xFFFE) and (w & 0xFFF) >= 0x200:
                            glyph_use[w & 0xFFF] += 1
    # 2×2 글리프 띠 (캐릭터 선택 화면)
    strips = []
    for s in L.STRIPS:
        p = L.strip_parse(img, s["addr"])
        strips.append({"id": f"S:{s['addr']:06x}", "label": s["label"], "type": "S", "addr": f"{s['addr']:06x}", "end": f"{s['addr'] + 48:06x}",
                       "size": 48, "bases": [f"{b:03x}" for b in p["bases"]], "pal": p["pal"], "ascii": p["ascii"], "ascii_pal": p["ascii_pal"],
                       "rows": [[f"{w:04x}" for w in r] for r in p["rows"]]})
        for b in p["bases"]:
            glyph_use[b] += 1
    out["blocks"].append({"id": "T:strips", "label": "class_select_strips", "type": "table", "entries": strips, "pointers": []})
    out["glyph_usage"] = {f"{k:03x}": v for k, v in sorted(glyph_use.items())}
    out["unique_glyphs"] = len(glyph_use)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n_a = sum(1 for b in out["blocks"] for r in (b.get("entries") or [b]) if r["type"] == "A")
    print(f"[OK] {OUT.relative_to(L.ROOT)}: blocks={len(out['blocks'])} A-scripts={n_a} unique 16x16 glyphs={len(glyph_use)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
