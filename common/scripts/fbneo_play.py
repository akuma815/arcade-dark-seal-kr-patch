"""FBNeo 를 게임·IPS·Lua 와 함께 띄우고 그대로 둔다 (사람이 플레이하며 QA). 종료는 사용자가 한다.

사용: python common/scripts/fbneo_play.py <game> [--ips NAME] [--lua script.lua] [--load-state]
FBNeo 퀵 세이브 = F10 (savestates/<game> slot 01.fs), 퀵 로드 = F9. --load-state 는 기동 후 F9 를 창 메시지로 보낸다.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fbneo_lua import launch, open_console_and_run, user32, wait_main_window  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--ips")
    ap.add_argument("--lua")
    ap.add_argument("--load-state", action="store_true", help="기동 후 퀵 로드(F9) — savestates/<game> slot 01.fs 가 있어야 함")
    ap.add_argument("--load-delay", type=float, default=6.0)
    a = ap.parse_args()
    extra = ["-ips", a.ips] if a.ips else None
    p = launch(a.game, extra)
    hwnd = wait_main_window(p)
    if a.lua:
        time.sleep(1.0)
        open_console_and_run(p, hwnd, Path(a.lua).resolve())
    if a.load_state:
        time.sleep(a.load_delay)
        user32.PostMessageW(hwnd, 0x100, 0x78, 1)            # WM_KEYDOWN VK_F9
        time.sleep(0.15)
        user32.PostMessageW(hwnd, 0x101, 0x78, 1 | (1 << 30) | (1 << 31))
        print("[OK] 퀵 로드(F9) 전송")
    print(f"[OK] FBNeo pid={p.pid} 실행 중: {a.game} ips={a.ips or '-'} lua={a.lua or '-'} (창을 닫으면 종료)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
