"""번역 원장(SSOT) 생성/갱신: workspace/text/translation/ds1_translation.json

원천: source/ds1_blocks.json(글리프 열) + font/mapping/ds1_glyph_map.json(전사) → 스크립트별
  - id, label, source_rows(원문 줄, 전각 공백 = 빈 셀), layout(원본 행 수·최대 셀 폭·선두 여백·세로쓰기 여부·팔레트)
  - ko_rows: 번역 줄 목록 (한 줄 = 셀 열, 공백 1자 = 빈 셀 1개). 비어 있으면 미번역
  - status: untranslated | draft | needs_review | approved
기존 원장이 있으면 ko_rows/status/notes 는 보존하고 source/layout 만 갱신한다.
사용: python darksealj/workspace/scripts/make_ledger.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds1lib as L  # noqa: E402

SRC = L.GAME / "workspace" / "text" / "source"
MAP = L.GAME / "workspace" / "font" / "mapping" / "ds1_glyph_map.json"
LEDGER = L.GAME / "workspace" / "text" / "translation" / "ds1_translation.json"


def main() -> int:
    blocks = json.loads((SRC / "ds1_blocks.json").read_text(encoding="utf-8"))
    m = json.loads(MAP.read_text(encoding="utf-8"))
    old = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {"entries": []}
    keep = {e["id"]: e for e in old.get("entries", [])}
    entries = []
    seen = set()
    for b in blocks["blocks"]:
        for r in (b.get("entries") or [b]):
            if r["id"] in seen:
                continue
            if r["type"] == "S":
                seen.add(r["id"])
                src = "".join(m.get(h, f"〔{h}〕") for h in r["bases"])
                entries.append({
                    "id": r["id"], "label": r["label"], "addr": r["addr"], "size_bytes": r["size"],
                    "source_rows": [src], "ascii_row": r["ascii"],
                    "layout": {"rows": 1, "max_cells": 4, "lead_blank": 0, "vertical_original": False, "palettes": [r["pal"]],
                               "note": "8셀 폭 띠, 글리프 ≤4, 가운데 정렬"},
                    "ko_rows": keep.get(r["id"], {}).get("ko_rows", []),
                    "status": keep.get(r["id"], {}).get("status", "untranslated"),
                    "notes": keep.get(r["id"], {}).get("notes", ""),
                })
                continue
            if r["type"] == "C" and r["label"].startswith("profile"):
                seen.add(r["id"])
                entries.append({
                    "id": r["id"], "label": r["label"], "addr": r["addr"], "size_bytes": r["size"],
                    "source_items": [{"off": it["tilemap_byte_off"], "row": it["row"], "col": it["col"], "text": it["text"]} for it in r["items"]],
                    "layout": {"note": "8×8 타일 문자열(라우틴 C→C2). off 는 0x262000 기준 바이트 오프셋, 열 = off/2 % 64. 화면 폭 32열"},
                    "ko_items": keep.get(r["id"], {}).get("ko_items", []),
                    "status": keep.get(r["id"], {}).get("status", "untranslated"),
                    "notes": keep.get(r["id"], {}).get("notes", ""),
                })
                continue
            if r["type"] != "A":
                continue
            seen.add(r["id"])
            rows = []
            for row in r["rows"]:
                s = ""
                for h in row:
                    w = int(h, 16)
                    if w == 0:
                        s += "　"
                    elif (w & 0xFFF) < 0x80:
                        s += chr(w & 0x7F)
                    else:
                        s += m.get(f"{w & 0xFFF:03x}", f"〔{w & 0xFFF:03x}〕")
                rows.append(s)
            widths = [len(row) for row in r["rows"]]
            lead = min((len(row) - len(row.lstrip("　")) for row in rows if row.strip("　")), default=0)
            # 세로쓰기 판정: 행 수가 셀 폭보다 훨씬 크고 행마다 글리프가 띄엄띄엄
            vertical = len(rows) >= 10 and max(widths) >= 12 and all(len(row.strip("　")) <= 15 for row in rows)
            e = {
                "id": r["id"], "label": r["label"], "addr": r["addr"], "size_bytes": r["size"],
                "source_rows": rows,
                "layout": {"rows": len(rows), "max_cells": max(widths) if widths else 0, "lead_blank": lead,
                           "vertical_original": vertical, "palettes": r["palettes"]},
                "ko_rows": keep.get(r["id"], {}).get("ko_rows", []),
                "status": keep.get(r["id"], {}).get("status", "untranslated"),
                "notes": keep.get(r["id"], {}).get("notes", ""),
            }
            entries.append(e)
    out = {"_schema": "ds1_translation v1", "_rules": {
        "cell": "16×16 글리프 1개 = 1셀. 공백 1자 = 빈 셀 1개(0x0000). 줄 끝 공백은 생략 가능",
        "ko_rows": "줄 목록. 각 줄의 셀 수(글자+공백) ≤ layout.max_cells 를 기본 상한으로 하되 화면 폭(16셀) 안에서 조정 가능",
        "status": "untranslated → draft(모델 초벌) → needs_review → approved(사람)"},
        "entries": entries}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {LEDGER.relative_to(L.ROOT)}: entries={len(entries)}")
    for e in entries:
        lay = e["layout"]
        if "rows" in lay:
            print(f"  {e['id']} {e['label']:<16} rows={lay['rows']:2d} max_cells={lay['max_cells']:2d} lead={lay['lead_blank']} vert={lay['vertical_original']} status={e['status']}")
        else:
            print(f"  {e['id']} {e['label']:<16} items={len(e.get('source_items', []))} status={e['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
