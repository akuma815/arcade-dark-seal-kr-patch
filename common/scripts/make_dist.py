"""배포 zip 생성: FBNeo IPS 패치 세트 + 적용법 + SHA-256. 원본 ROM 은 절대 포함하지 않는다.

입력: <게임>/build/<name>/ 의 <name>.dat, <name>-*.ips, report.json
출력: <게임>/dist/<zipname>/ 와 <zipname>.zip — 안에 support/ips/<세트>/… (FBNeo 폴더에 그대로 풀면 되는 구조)
사용: python common/scripts/make_dist.py darksealj --name Korean --version 1.0 [--set darksealj]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TITLES = {"darksealj": "Dark Seal (Japan rev 4)", "darkseal2": "Dark Seal 2 (Japan v2.1)"}
PARENTS = {"darksealj": "darkseal", "darkseal2": "wizdfire"}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--name", default="Korean")
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--set", dest="setname", default=None)
    a = ap.parse_args()
    setname = a.setname or a.game
    build = ROOT / a.game / "build" / a.name
    dat = build / f"{a.name}.dat"
    if not dat.exists():
        raise SystemExit(f"빌드 없음: {dat} — build_translation.py --name {a.name} 먼저")
    report = json.loads((build / "report.json").read_text(encoding="utf-8"))
    date = dt.date.today().strftime("%Y%m%d")
    zipname = f"{setname}_KR_v{a.version}_{date}"
    out = ROOT / a.game / "dist" / zipname
    if out.exists():
        shutil.rmtree(out)
    ipsdir = out / "support" / "ips" / setname
    ipsdir.mkdir(parents=True)
    files = [dat] + sorted(build.glob(f"{a.name}-*.ips"))
    for f in files:
        shutil.copy(f, ipsdir / f.name)
    roms = report["roms"]
    readme = f"""{TITLES.get(setname, setname)} 한글 패치 v{a.version} ({date})

■ 형식
  FBNeo(FinalBurn Neo) IPS 패치. 원본 ROM 파일은 포함되어 있지 않습니다.
  지원 세트: {setname} (부모 세트 {PARENTS.get(setname, '-')} 포함, MAME 0.2xx 계열 ROM 이름/CRC 기준)

■ 적용 방법 (FBNeo v1.0.0.03 기준)
  1. 이 zip 안의 support 폴더를 FBNeo 설치 폴더에 그대로 덮어씁니다.
     → FBNeo\\support\\ips\\{setname}\\{a.name}.dat 와 {a.name}-*.ips 가 생깁니다.
  2. FBNeo 에서 {setname} 을 선택한 뒤 "IPS Manager"(게임 메뉴) 에서 "{a.name}" 패치를 체크하고 실행합니다.
     또는 명령줄: fbneo64.exe {setname} -ips {a.name}
  3. 패치는 실행 시 메모리에서만 적용되며 원본 zip 은 수정되지 않습니다.

■ 패치가 바꾸는 ROM ({len(roms)}개)
""" + "\n".join(f"  {name:<14} 원본 CRC {report['roms'][name].get('crc', '')} ({v['changed_bytes']} 바이트 변경, {v['ips']})" for name, v in roms.items()) + f"""

■ 주의
  - 클론 세트 전용 패치입니다. 부모 세트({PARENTS.get(setname, '-')})만 실행하면 적용되지 않습니다.
  - 다른 버전의 ROM(CRC 불일치)에는 적용되지 않습니다.
  - 폰트: Galmuri (SIL OFL 1.1, https://github.com/quiple/galmuri)

■ 파일 무결성
  SHA256.txt 참고
"""
    (out / "README_KO.txt").write_text(readme, encoding="utf-8")
    lines = []
    for f in sorted(out.rglob("*")):
        if f.is_file() and f.name != "SHA256.txt":
            lines.append(f"{sha256(f)}  {f.relative_to(out).as_posix()}")
    (out / "SHA256.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "release_report.json").write_text(json.dumps({"set": setname, "name": a.name, "version": a.version, "date": date,
                                                         "roms": roms, "scripts": report.get("scripts"), "untranslated": report.get("untranslated")},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
    zpath = out.parent / (zipname + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out).as_posix())
    bad = [n for n in zipfile.ZipFile(zpath).namelist() if n.lower().endswith((".zip", ".bin")) or "/roms/" in n.lower()]
    if bad:
        raise SystemExit(f"배포물에 ROM 류 파일 포함: {bad}")
    print(f"[OK] {zpath.relative_to(ROOT)} ({zpath.stat().st_size} bytes) sha256={sha256(zpath)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
