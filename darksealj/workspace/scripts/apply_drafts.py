"""초벌/수정 파일(drafts_*.json)을 원장에 반영하고 레이아웃을 검사한다.

검사: 각 줄 셀 수 ≤ 상한(본문 14, 프롤로그 14), 줄 수 ≤ 상한(본문 4, 프롤로그 14), 글리프 공급 가능 여부(한글 음절·원문 글리프 표에 있는 문장부호·ASCII).
위반은 보고만 하고(빌드에서 차단) 원장에는 기록한다. 상태는 draft 로 둔다(사람 승인은 별도).
사용: python darksealj/workspace/scripts/apply_drafts.py darksealj/workspace/text/translation/drafts_v1.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds1lib as L  # noqa: E402

LEDGER = L.GAME / "workspace" / "text" / "translation" / "ds1_translation.json"
MAP = L.GAME / "workspace" / "font" / "mapping" / "ds1_glyph_map.json"
LIMITS = {"prologue": (14, 14), "rank_names": (8, 9), "default": (14, 4)}   # (max cells per line, max lines)
HANDMADE_PUNCT = set(",.()")                           # build_poc 의 수제 마스크


def is_hangul(c: str) -> bool:
    return 0xAC00 <= ord(c) <= 0xD7A3


def main() -> int:
    drafts = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    gmap = json.loads(MAP.read_text(encoding="utf-8"))
    reusable = set(gmap.values())                      # 원문 글리프 표에 있는 문자(문장부호·따옴표 등)는 기존 타일 재사용
    by_id = {e["id"]: e for e in ledger["entries"]}
    problems = []
    hangul = Counter()
    for sid, d in drafts.items():
        if sid.startswith("_") or sid not in by_id:
            continue
        e = by_id[sid]
        if "ko_items" in d:                                   # 프로필(C2) 항목: [{"off": "0296", "text": "이름-"}]
            for it in d["ko_items"]:
                col = (int(it["off"], 16) // 2) % 64
                if col + len(it["text"]) > 32:
                    problems.append(f"{sid} {e['label']} off={it['off']}: 열 {col}+{len(it['text'])} > 32: {it['text']}")
                for c in it["text"]:
                    if is_hangul(c):
                        hangul[c] += 1
            e["ko_items"] = d["ko_items"]
            e["status"] = "draft"
            if d.get("notes"):
                e["notes"] = d["notes"]
            continue
        rows = d["ko_rows"]
        maxc, maxl = LIMITS.get(e["label"], LIMITS["default"])
        if len(rows) > maxl:
            problems.append(f"{sid} {e['label']}: {len(rows)}줄 > {maxl}")
        for i, row in enumerate(rows):
            if len(row) > maxc:
                problems.append(f"{sid} {e['label']} 줄{i + 1}: {len(row)}셀 > {maxc}: {row}")
            for c in row:
                if c == " ":
                    continue
                if is_hangul(c):
                    hangul[c] += 1
                elif c in reusable or c in HANDMADE_PUNCT or c.isascii():
                    pass
                else:
                    problems.append(f"{sid} 줄{i + 1}: 공급 불가 문자 '{c}'")
        e["ko_rows"] = rows
        e["status"] = "draft"
        if d.get("notes"):
            e["notes"] = d["notes"]
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    n_draft = sum(1 for e in ledger["entries"] if e["status"] == "draft")
    print(f"[OK] ledger updated: draft={n_draft}/{len(ledger['entries'])}, 고유 한글 {len(hangul)}자 (출현 {sum(hangul.values())})")
    for p in problems:
        print("  [!]", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
