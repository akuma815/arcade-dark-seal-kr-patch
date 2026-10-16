"""Dark Seal 1 번역 빌드: 원장(ds1_translation.json) → 패치 ROM + FBNeo IPS 세트.

절차
 1. 원본 로드·무변경 왕복 검사
 2. 글리프 배정: 번역문의 한글/수제 문장부호 → (a) 번역된 스크립트가 쓰던 일본어 글리프 중 미번역 스크립트가 쓰지 않는 슬롯,
    (b) 부족하면 0xa00~0xfff. 원문 글리프 표에 있는 문장부호(、。“”！‼‥ 등)는 기존 타일 재사용(해제 대상에서 제외)
 3. 스크립트 방출: ko_rows 가 있는 항목(상태 draft 이상)은 교체, 나머지는 원본 유지. 원본 블록 크기 초과 시 실패
 4. 프롤로그: 세로 크롤 패치(PoC-2) + 후리가나 블록 무효화
 5. Expected Write → build/kr/ ROM·IPS·dat, FBNeo support/ips/darksealj/ 설치, build/kr/report.json
사용: python darksealj/workspace/scripts/build_translation.py [--name kr] [--no-install] [--min-status draft]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ds1lib as L  # noqa: E402

sys.path.insert(0, str(L.ROOT / "common" / "scripts"))
from patchutil import check_allowed, crc32, ips_build  # noqa: E402

LEDGER = L.GAME / "workspace" / "text" / "translation" / "ds1_translation.json"
GMAP = L.GAME / "workspace" / "font" / "mapping" / "ds1_glyph_map.json"
FONT16 = L.ROOT / "inputs" / "fonts" / "Galmuri11_16x16.png"
FBNEO_IPS = Path(r"H:\FBNeo v1.0.0.03\support\ips\darksealj")
STATUS_RANK = {"untranslated": 0, "draft": 1, "needs_review": 2, "approved": 3}
FALLBACK_BANK = (0xA00, 0x1000)

PUNCT_MASKS = {
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
    "?": ["................", "................", "....####........", "...#....#.......", "........#.......", ".......#........",
          "......#.........", "......#.........", "................", "......#.........", "......#.........", "................",
          "................", "................", "................", "................"],
    "!": ["................", "................", "......#.........", "......#.........", "......#.........", "......#.........",
          "......#.........", "......#.........", "................", "......#.........", "......#.........", "................",
          "................", "................", "................", "................"],
}


def is_hangul(c: str) -> bool:
    return 0xAC00 <= ord(c) <= 0xD7A3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="kr")
    ap.add_argument("--desc", default="Dark Seal Korean (dev build)|다크씰 한글 (개발 빌드)", help="dat 설명 'en|ko'")
    ap.add_argument("--min-status-release", action="store_true", help="approved 항목만 포함 (릴리즈)")
    ap.add_argument("--no-install", action="store_true")
    ap.add_argument("--min-status", default="draft")
    ap.add_argument("--step-mask", type=lambda v: int(v, 0), default=3)
    ap.add_argument("--start-row", type=int, default=30)
    a = ap.parse_args()
    min_rank = STATUS_RANK["approved"] if a.min_status_release else STATUS_RANK[a.min_status]

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    gmap = json.loads(GMAP.read_text(encoding="utf-8"))          # "2b4" -> "民"
    rev = {}
    for k, v in gmap.items():
        rev.setdefault(v, int(k, 16))                            # 문자 -> 기존 글리프 base (문장부호 재사용용)

    prg_files, chr_region = L.load_originals()
    img = L.prg_decode(prg_files)
    assert L.prg_encode(img) == prg_files and L.chr_encode(L.chr_decode(chr_region)) == chr_region, "왕복 실패"
    tiles = L.chr_decode(chr_region)

    entries = ledger["entries"]
    translated = [e for e in entries if (e.get("ko_rows") or e.get("ko_items")) and STATUS_RANK[e["status"]] >= min_rank]
    untranslated = [e for e in entries if e not in translated]

    # 2. 글리프 배정
    blocks = json.loads((L.GAME / "workspace" / "text" / "source" / "ds1_blocks.json").read_text(encoding="utf-8"))
    raw_by_id = {r["id"]: r for b in blocks["blocks"] for r in (b.get("entries") or [b]) if r["type"] in ("A", "S")}

    def script_glyph_set(sid):
        r = raw_by_id[sid]
        if r["type"] == "S":
            return {int(h, 16) for h in r["bases"]}
        return {int(h, 16) & 0xFFF for row in r["rows"] for h in row if int(h, 16) not in (0, 0xFFFE) and (int(h, 16) & 0xFFF) >= 0x200}

    keep = set()
    for e in untranslated:
        if e["id"] in raw_by_id:
            keep |= script_glyph_set(e["id"])
    # 보수적 보존: 데이터 영역에서 등록된 A/S 블록 밖에 있는 글리프형 워드(팔레트 0/6/7/9, base 0x200~0x9ff, 짝수)의 base 를 전부 보존
    known_spans = [(int(r["addr"], 16), int(r["end"], 16)) for r in raw_by_id.values()]
    unknown_refs = set()
    for off in range(L.DATA_REGION[0], L.DATA_REGION[1], 2):
        if any(s <= off < e for s, e in known_spans):
            continue
        w = int.from_bytes(img[off:off + 2], "big")
        t = w & 0xFFF
        if (w >> 12) in (0, 6, 7, 9) and 0x200 <= t <= 0x9FF and (t & 1) == 0:
            unknown_refs.add(t & ~3)
    keep |= unknown_refs
    print(f"[info] 데이터 영역 미등록 글리프 참조(보존): {len(unknown_refs)}")
    needed_chars = []
    for e in translated:
        if e["label"] == "rank_names":                 # 8×8 타일 경로 (아래 3d)
            continue
        for row in e.get("ko_rows", []):
            for c in row:
                if c != " " and c not in needed_chars:
                    needed_chars.append(c)
    reuse = {c: rev[c] for c in needed_chars if not is_hangul(c) and c in rev and c not in PUNCT_MASKS}
    keep |= set(reuse.values())
    new_chars = [c for c in needed_chars if c not in reuse]
    freed = sorted({g for e in translated if e["id"] in raw_by_id for g in script_glyph_set(e["id"])} - keep)
    pool = freed + [g for g in range(FALLBACK_BANK[0], FALLBACK_BANK[1], 4)]
    if len(new_chars) > len(pool):
        raise SystemExit(f"글리프 슬롯 부족: 필요 {len(new_chars)} > 가용 {len(pool)}")
    alloc = {c: pool[i] for i, c in enumerate(new_chars)}
    n_fallback = sum(1 for g in alloc.values() if g >= FALLBACK_BANK[0])
    print(f"[OK] 글리프: 재사용 {len(reuse)}, 신규 {len(new_chars)} (해제 일본어 슬롯 {len(freed)} 중 {len(new_chars) - n_fallback} 사용, 0xa00+ {n_fallback}), 보존 {len(keep)}")

    sheet = Image.open(FONT16).convert("RGBA")
    missing = []
    for c, base in alloc.items():
        if is_hangul(c):
            m11 = L.hangul_sheet_glyph(sheet, c, 16)
            mask = [[0] * 16 for _ in range(16)]
            for y in range(11):
                for x in range(11):
                    mask[y + 2][x + 2] = m11[y][x]
        elif c in PUNCT_MASKS:
            mask = [[1 if ch == "#" else 0 for ch in row] for row in PUNCT_MASKS[c]]
        else:
            missing.append(c)
            continue
        L.glyph_to_16x16(tiles, base, L.mask_to_glyph(mask))
    if missing:
        raise SystemExit(f"글리프를 만들 수 없는 문자: {missing}")

    # 3. 스크립트 방출 — 아레나 단위 재배치 (같은 포인터 테이블/즉시값이 가리키는 연속 영역 안에서 다시 깐다)
    def emit(e):
        lead = e["layout"]["lead_blank"] if e["label"] != "prologue" else 1
        words = []
        for row in e["ko_rows"]:
            words += [0] * lead
            for c in row:
                words.append(0 if c == " " else (reuse.get(c) if c in reuse else alloc[c]))
            words.append(0xFFFE)
        return L.script_emit(words)

    by_id = {e["id"]: e for e in entries}
    tr_ids = {e["id"] for e in translated}
    new_img = bytearray(img)
    allowed = []
    report_scripts = []
    for arena in L.SCRIPT_ARENAS:
        start, end = arena["span"]
        # 아레나 안의 스크립트들(원본 주소 순, 중복 포인터는 하나로)
        if "table" in arena:
            taddr, n = arena["table"]
            ptrs = [int.from_bytes(img[taddr + i * 4:taddr + i * 4 + 4], "big") for i in range(n)]
        else:
            ptrs = [arena["script"]]
        uniq = sorted(set(ptrs))
        cur = start
        newaddr, newlen = {}, {}
        for p in uniq:
            sid = f"A:{p:06x}"
            if sid in tr_ids:
                data = emit(by_id[sid])
            else:
                _, pend = L.script_parse(img, p)
                data = bytes(img[p:pend])                     # 미번역: 원본 바이트 그대로 이동
            if cur + len(data) > end:
                raise SystemExit(f"아레나 {arena['name']} 공간 부족 ({sid} 에서 {cur + len(data) - end}B 초과)")
            new_img[cur:cur + len(data)] = data
            newaddr[p], newlen[p] = cur, len(data)
            if sid in tr_ids:
                report_scripts.append({"id": sid, "label": by_id[sid]["label"], "bytes": len(data), "new_addr": f"{cur:06x}", "lines": len(by_id[sid]["ko_rows"])})
            cur += len(data)
        new_img[cur:end] = b"\xff" * (end - cur)              # 남는 공간은 0xff 로 채운다
        allowed.append((start, end))
        if "table" in arena:
            taddr, n = arena["table"]
            for i, p in enumerate(ptrs):
                new_img[taddr + i * 4:taddr + i * 4 + 4] = newaddr[p].to_bytes(4, "big")
            allowed.append((taddr, taddr + n * 4))
        else:
            for imm in arena["immediates"]:
                new_img[imm:imm + 4] = newaddr[arena["script"]].to_bytes(4, "big")
                allowed.append((imm, imm + 4))
        if arena.get("ffff_immediates"):                      # 후리가나 B 블록 호출자 → 0xffff(스크립트 끝) 로 돌린다
            tail = newaddr[arena["script"]] + newlen[arena["script"]] - 2   # 스크립트 마지막 워드 = 0xffff
            for imm in arena["ffff_immediates"]:
                new_img[imm:imm + 4] = tail.to_bytes(4, "big")
                allowed.append((imm, imm + 4))

    # 3b. 띠(S) 방출
    for e in translated:
        if not e["id"].startswith("S:"):
            continue
        raw = raw_by_id[e["id"]]
        text = e["ko_rows"][0].replace(" ", "")
        if len(text) > 4:
            raise SystemExit(f"{e['id']} {e['label']}: 띠는 4셀 이하: {text}")
        bases = [reuse[c] if c in reuse else alloc[c] for c in text]
        ascii_row = [int(h, 16) for h in raw["rows"][2]]
        data = L.strip_emit(bases, raw["pal"], ascii_row)
        addr = int(raw["addr"], 16)
        new_img[addr:addr + 48] = data
        allowed.append((addr, addr + 48))
        report_scripts.append({"id": e["id"], "label": e["label"], "bytes": 48, "new_addr": f"{addr:06x}", "lines": 1})

    # 3c. 8×8 한글 타일(프로필 C2 + 계급명): 문자 ROM 꼭대기(0xfff)부터 아래로 배정. 프로필 데이터·코드는 ROM 꼬리 빈 공간에
    prof = [e for e in translated if e["id"].startswith("C:") and e.get("ko_items")]
    rank = next((e for e in translated if e["label"] == "rank_names"), None)
    tiles8_used = 0
    alloc8 = {}
    if prof or rank:
        chars8 = []
        for e in prof:
            for it in e["ko_items"]:
                for c in it["text"]:
                    if is_hangul(c) and c not in chars8:
                        chars8.append(c)
        if rank:
            for name in rank["ko_rows"]:
                for c in name:
                    if is_hangul(c) and c not in chars8:
                        chars8.append(c)
        top16 = max(alloc.values(), default=FALLBACK_BANK[0]) + 4          # 16×16 배정이 끝난 다음 타일
        sheet8 = Image.open(L.ROOT / "inputs" / "fonts" / "Galmuri7_8x8.png").convert("RGBA")
        t = 0xFFF
        for c in chars8:
            if t < top16:
                raise SystemExit("8×8 한글 타일 슬롯 부족 (16×16 배정과 충돌)")
            tiles[t] = L.hangul8_tile(L.hangul_sheet_glyph(sheet8, c, 8))
            alloc8[c] = t
            t -= 1
        tiles8_used = len(alloc8)
    if rank:
        raw = raw_by_id[rank["id"]]
        pal = raw["palettes"][0] if raw["palettes"] else 9
        words = []
        for name in rank["ko_rows"]:
            if len(name) > 8:
                raise SystemExit(f"계급명 8셀 초과: {name}")
            field = [(pal << 12) | (alloc8[c] if is_hangul(c) else ord(c)) for c in name if c != " "]
            pad = (8 - len(field)) // 2                                   # 원문처럼 가운데 정렬
            words += [0] * pad + field + [0] * (8 - len(field) - pad)
        data = L.script_emit(words)
        addr, size = int(raw["addr"], 16), raw["size"]
        if len(data) != size:
            raise SystemExit(f"계급명 블록 크기 불일치 {len(data)} != {size}")
        new_img[addr:addr + size] = data
        allowed.append((addr, addr + size))
        report_scripts.append({"id": rank["id"], "label": "rank_names", "bytes": size, "new_addr": f"{addr:06x}", "lines": 9})
    if prof:
        labels = next((e for e in prof if e["label"] == "profile_labels"), None)
        values = sorted((e for e in prof if e["label"].startswith("profile_values")), key=lambda e: e["label"])
        if labels is None or len(values) != 4:
            raise SystemExit("프로필 번역은 라벨 1 + 값 4 가 모두 있어야 한다")

        def enc_items(e):
            items = []
            for it in e["ko_items"]:
                words = []
                for c in it["text"]:
                    if is_hangul(c):
                        words.append(alloc8[c])
                    elif c == " ":
                        words.append(0x20)
                    elif c.isascii() and c.isprintable():
                        words.append(ord(c))
                    else:
                        raise SystemExit(f"프로필 문자 공급 불가 '{c}'")
                items.append((int(it["off"], 16), words))
            return L.c2_encode(items)

        free = L.FREE_SPACE[0]
        c2_addr = free
        new_img[free:free + len(L.C2_CODE)] = L.C2_CODE
        free += len(L.C2_CODE)
        free += free & 1
        labels_addr = free
        d = enc_items(labels)
        new_img[free:free + len(d)] = d
        free += len(d) + (len(d) & 1)
        val_addrs = []
        for e in values:
            d = enc_items(e)
            val_addrs.append(free)
            new_img[free:free + len(d)] = d
            free += len(d) + (len(d) & 1)
        table_addr = free
        for ad in val_addrs:
            new_img[free:free + 4] = ad.to_bytes(4, "big")
            free += 4
        setup_addr = free
        code = L.profile_setup_code(labels_addr, table_addr, c2_addr)
        new_img[free:free + len(code)] = code
        free += len(code)
        if free > L.FREE_SPACE[1]:
            raise SystemExit("빈 공간 부족")
        s, en = L.PROFILE_SETUP
        hook = b"\x4e\xf9" + setup_addr.to_bytes(4, "big")              # jmp setup.l
        new_img[s:en] = hook + b"\x4e\x71" * ((en - s - len(hook)) // 2)
        allowed += [(L.FREE_SPACE[0], free), (s, en)]
        for e in prof:
            report_scripts.append({"id": e["id"], "label": e["label"], "bytes": len(enc_items(e)), "new_addr": "freespace", "lines": len(e["ko_items"])})
        print(f"[OK] 프로필: 8×8 한글 {tiles8_used}타일 (0x{t + 1:03x}~0xfff), C2 코드 {c2_addr:06x}, 데이터 {labels_addr:06x}.., 설정 루틴 {setup_addr:06x}, 빈 공간 사용 {free - L.FREE_SPACE[0]}B")

    # 4. 프롤로그 크롤 패치
    pro = next((e for e in translated if e["label"] == "prologue"), None)
    if pro:
        s, en = L.PROLOGUE_TEXT_SCROLL_ROUTINE
        if len(pro["ko_rows"]) * 16 > 224:
            raise SystemExit("프롤로그 14줄 초과")
        new_img[s:en] = L.prologue_vertical_scroll_code(step_mask=a.step_mask, y_stop=240 - 16)
        new_img[L.PROLOGUE_TEXT_X_INIT_IMM:L.PROLOGUE_TEXT_X_INIT_IMM + 2] = b"\x00\x00"
        a2 = L.TEXT_RAM + a.start_row * 128
        new_img[L.PROLOGUE_A2_IMM:L.PROLOGUE_A2_IMM + 4] = a2.to_bytes(4, "big")
        allowed += [(s, en), (L.PROLOGUE_TEXT_X_INIT_IMM, L.PROLOGUE_TEXT_X_INIT_IMM + 2), (L.PROLOGUE_A2_IMM, L.PROLOGUE_A2_IMM + 4)]

    # 5. Expected Write + 출력
    check_allowed(img, bytes(new_img), allowed, "prg")
    new_chr = L.chr_encode(tiles)
    allowed_chr = []
    for base in alloc.values():
        for off in L.PLANE_OFFS:
            allowed_chr.append((off + base * 8, off + (base + 4) * 8))
    for off in L.PLANE_OFFS:                                          # 8×8 한글 타일 (꼭대기부터)
        allowed_chr.append((off + (0x1000 - tiles8_used) * 8, off + 0x1000 * 8))
    check_allowed(chr_region, new_chr, allowed_chr, "chr")
    print(f"[OK] Expected Write 통과: 스크립트 {len(report_scripts)}개, 글리프 {len(alloc)}개")

    build = L.GAME / "build" / a.name
    build.mkdir(parents=True, exist_ok=True)
    orig_all = {**prg_files, **L.chr_split(chr_region)}
    new_all = {**L.prg_encode(bytes(new_img)), **L.chr_split(new_chr)}
    dat_lines, roms = [], {}
    for name, data in new_all.items():
        (build / name).write_bytes(data)
        if data != orig_all[name]:
            ips_name = f"{a.name}-{name.replace('.', '_')}"
            (build / f"{ips_name}.ips").write_bytes(ips_build(orig_all[name], data))
            dat_lines.append(f"{name}\t{ips_name}\tCRC({crc32(orig_all[name])})")
            roms[name] = {"changed_bytes": sum(1 for x, y in zip(orig_all[name], data) if x != y), "ips": ips_name + ".ips", "crc": crc32(orig_all[name])}
    desc_en, _, desc_ko = a.desc.partition("|")
    (build / f"{a.name}.dat").write_text("\n".join(dat_lines) + f"\n\n[en_US]\n{desc_en}\n\n[ko_KR]\n{desc_ko or desc_en}\n", encoding="utf-8")
    (build / "report.json").write_text(json.dumps({"scripts": report_scripts, "glyph_alloc": {c: f"{g:03x}" for c, g in alloc.items()},
                                                   "glyph_reuse": {c: f"{g:03x}" for c, g in reuse.items()}, "roms": roms,
                                                   "untranslated": [e["label"] for e in untranslated]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[OK] build:", ", ".join(f"{k} ({v['changed_bytes']}B)" for k, v in roms.items()))
    if not a.no_install:
        FBNEO_IPS.mkdir(parents=True, exist_ok=True)
        for f in [build / f"{a.name}.dat"] + list(build.glob(f"{a.name}-*.ips")):
            shutil.copy(f, FBNEO_IPS / f.name)
        print(f"[OK] FBNeo support/ips/darksealj/{a.name}.dat 설치")
    return 0


if __name__ == "__main__":
    sys.exit(main())
