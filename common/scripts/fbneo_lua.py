"""FBNeo(win32) 를 게임과 함께 띄운 뒤 Lua 콘솔을 Win32 메시지로 열어 스크립트를 실행하는 공용 러너.

FBNeo 커맨드라인은 ".lua" 를 첫 인자로만 받고 그 경우 게임을 시작하지 않는다(main.cpp ProcessCmdLine).
그래서 게임을 먼저 띄우고, 메인 창에 WM_COMMAND(ID_LUA_OPEN=11812) 를 보내 Lua 콘솔(IDD_LUA) 을 열고,
IDC_EDIT_LUAPATH(20368) 에 경로를 넣은 뒤 IDC_BUTTON_LUARUN(20366) 을 누른다. (ID 는 FBNeo resource.h)

다른 스크립트에서: from fbneo_lua import run_lua
  run_lua(game, lua_path, done_marker, timeout=120)  -> True/False
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time
from pathlib import Path

FBNEO_DIR = Path(r"H:\FBNeo v1.0.0.03")
FBNEO_EXE = FBNEO_DIR / "fbneo64.exe"

ID_LUA_OPEN = 11812
IDC_BUTTON_LUARUN = 20366
IDC_EDIT_LUAPATH = 20368
IDC_LUACONSOLE = 20369
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WM_COMMAND = 0x0111
WM_SETTEXT = 0x000C
BN_CLICKED = 0

user32 = ctypes.windll.user32
try:
    user32.SetProcessDPIAware()   # 창 좌표·캡처 크기를 물리 픽셀로 (DPI 배율 환경에서 잘림 방지)
except Exception:
    pass
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


def _windows_of_pid(pid: int) -> list[int]:
    found: list[int] = []

    def cb(hwnd, _):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def _title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def launch(game: str, extra: list[str] | None = None) -> subprocess.Popen:
    cmd = [str(FBNEO_EXE), game, "-w"] + (extra or [])
    return subprocess.Popen(cmd, cwd=str(FBNEO_DIR))


def wait_main_window(p: subprocess.Popen, timeout: float = 30) -> int:
    t0 = time.time()
    while time.time() - t0 < timeout:
        for h in _windows_of_pid(p.pid):
            if "FinalBurn Neo" in _title(h) and "•" in _title(h):
                return h
        if p.poll() is not None:
            raise RuntimeError("fbneo exited")
        time.sleep(0.3)
    raise TimeoutError("main window not found")


def open_console_and_run(p: subprocess.Popen, main_hwnd: int, lua_path: Path, timeout: float = 15) -> int:
    user32.PostMessageW(main_hwnd, WM_COMMAND, ID_LUA_OPEN, 0)
    t0 = time.time()
    while time.time() - t0 < timeout:
        for h in _windows_of_pid(p.pid):
            edit = user32.GetDlgItem(h, IDC_EDIT_LUAPATH)
            if edit:
                user32.SendMessageW(edit, WM_SETTEXT, 0, str(lua_path))
                btn = user32.GetDlgItem(h, IDC_BUTTON_LUARUN)
                user32.SendMessageW(h, WM_COMMAND, (BN_CLICKED << 16) | IDC_BUTTON_LUARUN, btn)
                return h
        time.sleep(0.3)
    raise TimeoutError("lua console not found")


def capture_window(hwnd: int, path: Path) -> None:
    """메인 창을 화면 캡처해 PNG 로 저장한다 (FBNeo gui.savescreenshot 은 경로 인자를 무시하므로 대체 수단)."""
    gdi32 = ctypes.windll.gdi32
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = r.right - r.left, r.bottom - r.top
    # Lua 콘솔 등 겹친 창의 영향을 받지 않도록 PrintWindow(PW_RENDERFULLCONTENT) 로 창 내용을 직접 받는다
    hdc = user32.GetDC(0)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    if not user32.PrintWindow(hwnd, mdc, 0x00000003):   # PW_CLIENTONLY | PW_RENDERFULLCONTENT
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        gdi32.BitBlt(mdc, 0, 0, w, h, hdc, pt.x, pt.y, 0x00CC0020)

    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                    ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                    ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

    bmi = BMIH(ctypes.sizeof(BMIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(0, hdc)
    from PIL import Image
    Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1).convert("RGB").save(path)


def console_text(pid: int) -> str:
    """Lua 콘솔 출력창의 텍스트 (스크립트 에러 메시지 확인용)."""
    for h in _windows_of_pid(pid):
        edit = user32.GetDlgItem(h, IDC_LUACONSOLE)
        if edit:
            n = user32.SendMessageW(edit, WM_GETTEXTLENGTH, 0, 0)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.SendMessageW(edit, WM_GETTEXT, n + 1, buf)
            return buf.value
    return ""


def run_lua(game: str, lua_path: Path, done_marker: Path, timeout: float = 120, keep_open: bool = False,
            extra_args: list[str] | None = None, screenshot: Path | None = None,
            watch: list[tuple[Path, Path]] | None = None, keys: list[tuple[float, int]] | None = None) -> bool:
    """extra_args 예: ["-ips", "poc"] (support/ips/<game>/poc.dat 적용). screenshot 지정 시 DONE 직후 창 캡처.
    watch: [(마커 파일, 캡처 경로)] — Lua 가 마커 파일을 만들면 즉시 창을 캡처한다 (프레임별 스크린샷)."""
    if done_marker.exists():
        done_marker.unlink()
    pending = list(watch or [])
    for m, _ in pending:
        if m.exists():
            m.unlink()
    p = launch(game, extra_args)
    ok = False
    try:
        main_hwnd = wait_main_window(p)
        time.sleep(1.0)
        open_console_and_run(p, main_hwnd, lua_path)
        t0 = time.time()
        key_queue = sorted(keys or [])
        while time.time() - t0 < timeout:
            while key_queue and time.time() - t0 >= key_queue[0][0]:
                _, vk = key_queue.pop(0)
                user32.SetForegroundWindow(main_hwnd)
                time.sleep(0.05)
                user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.1)
                user32.keybd_event(vk, 0, 2, 0)      # KEYEVENTF_KEYUP
            for m, shot in list(pending):
                if m.exists():
                    capture_window(main_hwnd, shot)
                    pending.remove((m, shot))
            if done_marker.exists():
                ok = True
                time.sleep(0.5)
                if screenshot is not None:
                    for h in _windows_of_pid(p.pid):          # Lua 콘솔을 닫아 게임 창만 남긴다
                        if user32.GetDlgItem(h, IDC_EDIT_LUAPATH):
                            user32.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE
                    time.sleep(0.5)
                    capture_window(main_hwnd, screenshot)
                break
            if p.poll() is not None:
                break
            time.sleep(0.05 if pending else 0.3)
        if not ok:
            print(f"[run_lua] not ok: elapsed={time.time() - t0:.0f}s, fbneo rc={p.poll()}, pending={len(pending)}")
            txt = console_text(p.pid)
            (done_marker.parent / "lua_console.txt").write_text(txt, encoding="utf-8")
            print("[lua console]", txt.strip()[-600:])
    finally:
        if not keep_open and p.poll() is None:
            p.kill()
    return ok


if __name__ == "__main__":
    # 간단 자가 테스트: python fbneo_lua.py <game> <script.lua> <done_marker>
    g, s, d = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    print("ok" if run_lua(g, s, d) else "FAILED")
