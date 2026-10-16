"""임의 Lua 스크립트를 FBNeo 에서 실행하는 커맨드라인 러너.

사용: python common/scripts/fbneo_run_lua.py <game> <script.lua> <done_marker> [--timeout N] [--ips NAME] [--screenshot PATH]
스크립트는 완료 시 done_marker 파일을 만들어야 한다. 실패 시 Lua 콘솔 텍스트를 done_marker 옆 lua_console.txt 에 남긴다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fbneo_lua import run_lua  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("lua")
    ap.add_argument("done")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--ips")
    ap.add_argument("--screenshot")
    a = ap.parse_args()
    extra = ["-ips", a.ips] if a.ips else None
    ok = run_lua(a.game, Path(a.lua).resolve(), Path(a.done).resolve(), timeout=a.timeout, extra_args=extra,
                 screenshot=Path(a.screenshot).resolve() if a.screenshot else None)
    print("ok" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
