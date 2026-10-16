"""FBNeo 를 Lua 스크립트와 함께 띄워 지정 프레임에서 메모리 범위를 파일로 덤프한다.

게임을 띄운 뒤 Lua 콘솔을 Win32 메시지로 열어 스크립트를 실행한다 (fbneo_lua.run_lua 참조 — 커맨드라인으로는 불가).
이 러너는 게임별 Lua 를 생성해 실행하고, 마지막 프레임 덤프가 끝날 때까지 기다린 뒤 프로세스를 종료한다.

사용 예:
  python common/scripts/fbneo_dump.py darksealj --frames 700 900 \
      --range 100000:4000 --range 200000:4000 --range 260000:4000 --range 140000:2000 --range 120000:800
출력: <게임>/work/dumps/<frame>/<addr>.bin, 같은 폴더의 screenshot_<frame>.png(가능한 경우), lua.log
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FBNEO_DIR = Path(r"H:\FBNeo v1.0.0.03")
FBNEO_EXE = FBNEO_DIR / "fbneo64.exe"

LUA_TEMPLATE = r"""
-- 자동 생성: fbneo_dump.py
local outdir = {outdir}
local frames = {{ {frames} }}
local ranges = {{ {ranges} }}
local log = io.open(outdir .. "/lua.log", "w")
local function L(s) log:write(s .. "\n"); log:flush() end
L("script loaded, framecount=" .. tostring(emu.framecount()))
local done = {{}}
local function dump(frame)
    os.execute('mkdir "' .. outdir:gsub("/", "\\") .. '\\' .. frame .. '" 2>nul')
    for _, r in ipairs(ranges) do
        local addr, len = r[1], r[2]
        local f = io.open(string.format("%s/%d/%06x.bin", outdir, frame, addr), "wb")
        local chunk = {{}}
        for i = 0, len - 1 do
            chunk[#chunk + 1] = string.char(memory.readbyte(addr + i))
            if #chunk >= 4096 then f:write(table.concat(chunk)); chunk = {{}} end
        end
        f:write(table.concat(chunk)); f:close()
        L(string.format("frame %d dumped %06x+%x", frame, addr, len))
    end
    local m = io.open(string.format("%s/CAP_%d", outdir, frame), "w"); m:write("x"); m:close()
    if gui and gui.savescreenshot then
        local ok, err = pcall(gui.savescreenshot, string.format("%s/%d/screenshot.png", outdir, frame))
        L("savescreenshot ok=" .. tostring(ok) .. " " .. tostring(err))
    end
end
local presses = {{ {presses} }}   -- {{frame, "P1 Coin"}} : 해당 프레임부터 4프레임 누름
emu.registerafter(function()
    local fc = emu.framecount()
    for _, pr in ipairs(presses) do
        if fc >= pr[1] and fc < pr[1] + 4 then
            local ok, err = pcall(joypad.set, {{ [pr[2]] = true }})    -- FBNeo: joypad.set(table) (플레이어 인덱스 없음)
            if fc == pr[1] then L("press " .. pr[2] .. " ok=" .. tostring(ok) .. " " .. tostring(err)) end
        end
    end
    for _, fr in ipairs(frames) do
        if fc >= fr and not done[fr] then
            done[fr] = true
            dump(fr)
            if fr == frames[#frames] then
                local f = io.open(outdir .. "/DONE", "w"); f:write("ok"); f:close()
                L("all done")
            end
        end
    end
end)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--frames", type=int, nargs="+", required=True)
    ap.add_argument("--range", action="append", required=True, help="hexaddr:hexlen")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--tag", default="")
    ap.add_argument("--ips", default=None, help="support/ips/<game>/<name>.dat 를 -ips 로 적용")
    ap.add_argument("--press", default=None, help="프레임:버튼 목록(Lua joypad), 예 400:P1 Coin,460:P1 Start")
    ap.add_argument("--keys", default=None, help="초:키 목록, 예 8:5,10:1 (8초에 5=코인, 10초에 1=스타트). 키는 한 글자(가상키 = 대문자 문자코드)")
    a = ap.parse_args()

    outdir = ROOT / a.game / "work" / ("dumps" + (("_" + a.tag) if a.tag else ""))
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("DONE"):
        f.unlink()
    ranges = []
    for r in a.range:
        addr, ln = r.split(":")
        ranges.append(f"{{0x{int(addr,16):x}, 0x{int(ln,16):x}}}")
    lua = LUA_TEMPLATE.format(
        outdir='"' + outdir.as_posix() + '"',
        frames=", ".join(str(f) for f in sorted(a.frames)),
        ranges=", ".join(ranges),
        presses=", ".join('{' + str(int(f)) + ', "' + b + '"}' for f, b in (kv.split(":", 1) for kv in a.press.split(","))) if a.press else "",
    )
    lua_path = outdir / "dump.lua"
    lua_path.write_text(lua, encoding="utf-8")

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fbneo_lua import run_lua

    print("run:", a.game, lua_path)
    extra = ["-ips", a.ips] if a.ips else None
    watch = [(outdir / f"CAP_{f}", outdir / f"screenshot_{f}.png") for f in sorted(a.frames)]
    keys = [(float(t), ord(k.upper())) for t, k in (kv.split(":") for kv in a.keys.split(","))] if a.keys else None
    ok = run_lua(a.game, lua_path, outdir / "DONE", timeout=a.timeout, extra_args=extra, screenshot=outdir / "screenshot.png", watch=watch, keys=keys)
    if not ok:
        print("timeout or early exit; no DONE marker")
    log = outdir / "lua.log"
    print(log.read_text(encoding="utf-8", errors="replace") if log.exists() else "(no lua.log — script never ran)")
    return 0 if (outdir / "DONE").exists() else 1


if __name__ == "__main__":
    sys.exit(main())
