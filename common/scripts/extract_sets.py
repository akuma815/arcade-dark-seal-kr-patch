"""original/*.zip 을 게임별 extracted/ 로 기계적으로 전개하고 rom_info.json 을 남긴다.

- original/ 에는 절대 쓰지 않는다.
- CRC32(zlib)·SHA-256 를 ROM 단위로 기록하고, zip 헤더 CRC 와 재계산 CRC 가 다르면 실패한다.
- 클론 세트는 <게임>/extracted/ 에, 부모 세트는 <게임>/extracted/parent/ 에 전개한다.
  (FBNeo 는 클론 zip 에 없는 ROM 을 부모 zip 에서 읽는다 — dat 의 merge 속성)
사용: python common/scripts/extract_sets.py   (어느 cwd 에서 실행해도 된다)
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# zip 파일명 → (게임 폴더, 하위 폴더, FBNeo 세트명, 비고)
# 세트명·부모 관계는 FBNeo v1.0.0.03 `-listinfo` dat 로 확인 (docs/fbneo_sets.xml)
SETS = {
    "darksealj.zip": ("darksealj", "",       "darksealj", "Dark Seal (Japan revision 4) — 클론, 번역 대상"),
    "darkseal.zip":  ("darksealj", "parent", "darkseal",  "Dark Seal (World revision 3) — 부모. GFX(mac-*)·사운드(fz_06-1)·샘플(fz_07/08)·fz_02/03"),
    "darkseal2.zip": ("darkseal2", "",       "darkseal2", "Dark Seal 2 (Japan v2.1) — 클론, 번역 대상. MAME 세트명은 darksel2"),
    "wizdfire.zip":  ("darkseal2", "parent", "wizdfire",  "Wizard Fire (Over Sea v2.1) — 부모. GFX(mas00~13)·PROM(mb7122h.16l)"),
}
# original/ 에 있지만 작업에 쓰지 않는 세트: darkseal1.zip(World rev1 클론), wizdfirea.zip(Over Sea v1.0 클론)
IGNORED = {"darkseal1.zip", "wizdfirea.zip"}


def main() -> int:
    ok = True
    for z in sorted((ROOT / "original").glob("*.zip")):
        if z.name not in SETS and z.name not in IGNORED:
            print(f"[UNKNOWN] {z.name} — SETS/IGNORED 에 등록되지 않은 zip")
            ok = False
    for zip_name, (game_dir, sub, set_name, note) in SETS.items():
        src = ROOT / "original" / zip_name
        if not src.exists():
            print(f"[MISSING] {src}")
            ok = False
            continue
        out = ROOT / game_dir / "extracted" / sub if sub else ROOT / game_dir / "extracted"
        out.mkdir(parents=True, exist_ok=True)
        info = {
            "source_zip": zip_name,
            "source_zip_size": src.stat().st_size,
            "source_zip_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
            "fbneo_set": set_name,
            "note": note,
            "roms": [],
        }
        with zipfile.ZipFile(src) as zf:
            for e in sorted(zf.infolist(), key=lambda i: i.filename):
                data = zf.read(e)
                crc = zlib.crc32(data) & 0xFFFFFFFF
                if crc != e.CRC:
                    print(f"[CRC MISMATCH] {zip_name}:{e.filename}")
                    ok = False
                (out / e.filename).write_bytes(data)
                info["roms"].append({
                    "name": e.filename,
                    "size": len(data),
                    "crc32": f"{crc:08x}",
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
        (out / "rom_info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] {zip_name} -> {out.relative_to(ROOT)}  ({len(info['roms'])} roms)")
        for r in info["roms"]:
            print(f"     {r['name']:<14} {r['size']:>8}  crc32={r['crc32']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
