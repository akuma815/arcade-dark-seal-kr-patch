"""실행 중인 FBNeo(fbneo64.exe) 에 Lua 스크립트를 붙여 실행한다 (프로세스 자동 탐지).

사용: python common/scripts/fbneo_attach.py <script.lua> [--done PATH] [--timeout N]
게임이 떠 있는 상태에서 메모리 덤프·세이브 등 즉시 실행용. 스크립트는 완료 시 --done 파일을 만들면 좋다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fbneo_lua as F  # noqa: E402


def fbneo_pids() -> list[int]:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq fbneo64.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    pids = []
    for line in out.splitlines():
        parts = [x.strip('"') for x in line.split('","')]
        if len(parts) > 1 and parts[0].lower().startswith("fbneo64"):
            pids.append(int(parts[1]))
    return pids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lua")
    ap.add_argument("--done")
    ap.add_argument("--timeout", type=float, default=30)
    a = ap.parse_args()
    pids = fbneo_pids()
    if not pids:
        print("FBNeo 가 실행 중이 아님")
        return 1
    pid = pids[-1]
    hwnd = next((h for h in F._windows_of_pid(pid) if "FinalBurn Neo" in F._title(h)), None)
    if hwnd is None:
        print("메인 창을 찾지 못함", pid)
        return 1
    F.user32.PostMessageW(hwnd, F.WM_COMMAND, F.ID_LUA_OPEN, 0)
    t0 = time.time()
    posted = False
    while time.time() - t0 < 15 and not posted:
        for h in F._windows_of_pid(pid):
            edit = F.user32.GetDlgItem(h, F.IDC_EDIT_LUAPATH)
            if edit:
                F.user32.SendMessageW(edit, F.WM_SETTEXT, 0, str(Path(a.lua).resolve()))
                btn = F.user32.GetDlgItem(h, F.IDC_BUTTON_LUARUN)
                F.user32.SendMessageW(h, F.WM_COMMAND, (F.BN_CLICKED << 16) | F.IDC_BUTTON_LUARUN, btn)
                posted = True
                break
        time.sleep(0.3)
    print(f"[attach] pid={pid} posted={posted}")
    if a.done:
        d = Path(a.done)
        t0 = time.time()
        while time.time() - t0 < a.timeout and not d.exists():
            time.sleep(0.3)
        print("[attach] done:", d.exists())
    txt = F.console_text(pid).strip()
    if txt:
        print("[lua console]", txt[-400:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
