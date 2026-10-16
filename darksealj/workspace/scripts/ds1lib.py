"""Dark Seal (darksealj) 형식 라이브러리 — docs/survey.md 의 규칙을 코드로 고정한다.

- 프로그램 ROM: 4개 파일 ↔ 0x80000 바이트 디코드 이미지 (인터리브 + BITSWAP08(7,1,5,4,3,2,6,0))
- 문자 ROM: fz_02.j1 + fz_03.j2 ↔ 4096개 8×8 4bpp 타일 (평면 0x00000/0x10000/0x08000/0x18000, 평면0=비트3)
- 글리프 스크립트(라우틴 A): 워드 열. pal<<12|k, 0=빈칸, 0xfffe=줄바꿈, 0xffff=끝
- 16×16 글리프 = 타일 k(TR), k+1(BR), k+2(TL), k+3(BL)
모든 encode 는 decode 의 역함수이며, 무변경 왕복은 build 에서 바이트 동일성으로 검사한다.
"""
from __future__ import annotations

from pathlib import Path

GAME = Path(__file__).resolve().parents[2]          # darksealj/
ROOT = GAME.parent                                  # Dark Seal/
EXTRACTED = GAME / "extracted"

PRG_FILES = [  # (파일명, 디코드 이미지 내 base, 바이트 오프셋 0=상위/1=하위)
    ("fz_04-4.j12", 0x00000, 0),
    ("fz_01-4.h14", 0x00000, 1),
    ("fz_00-2.h12", 0x40000, 0),
    ("fz_05-2.j14", 0x40000, 1),
]
CHR_FILES = ["parent/fz_02.j1", "parent/fz_03.j2"]
PLANE_OFFS = (0x00000, 0x10000, 0x08000, 0x18000)   # 평면 0(비트3)..3(비트0)

TEXT_RAM = 0x262000
SCRIPT_PROLOGUE = 0x7BA18
FURIGANA_PAIRS = 0x7BC0C
# 레이어↔스크롤 변수 (IRQ 0x18e~0x204 와 d_darkseal.cpp 의 제어 매핑으로 확정)
#   텍스트 레이어 pf_ram[1](0x262000) = 칩0 pf2 → 제어 0x2a0006/0x2a0008 ← RAM 0x10031c(X) / 0x100320(Y), 오프셋 없음
#   빨간 배경 pf_ram[3](0x202000)     = 칩1 pf2 → 제어 0x240006/0x240008 ← RAM 0x10038c-0x80 / 0x100390-0x80
TEXT_SCROLL_X = 0x10031C
TEXT_SCROLL_Y = 0x100320
# 프롤로그 설정(0xff54)은 텍스트 X 를 0x100 으로 두고, 루프가 매 프레임 부르는 0xffac 가 4프레임마다 X-1 → 0 에서 정지 (왼쪽에서 슬라이드 인)
PROLOGUE_TEXT_SCROLL_ROUTINE = (0xFFAC, 0xFFCC)
PROLOGUE_TEXT_X_INIT_IMM = 0xFF6A      # move.w #$100,$10031c 의 즉시값(2바이트)
PROLOGUE_A2_IMM = 0xFF8E               # movea.l #$262100,a2 의 즉시값(4바이트) — 스크립트가 써지는 타일맵 시작


# 글리프 스크립트(라우틴 A) 아레나: 같은 테이블/즉시값이 가리키는 연속 데이터 영역. 번역 빌드는 이 안에서 재배치한다.
#  span 은 [시작, 끝) — 끝은 다음 고정 데이터(테이블·B/C 블록)의 시작. 재배치 뒤 테이블 항목/즉시값을 갱신한다.
SCRIPT_ARENAS = [
    {"name": "prologue", "span": (0x7BA18, 0x7BC62), "script": 0x7BA18, "immediates": [0xFF94],
     "ffff_immediates": [0xFFA0]},                              # 0xff9e movea.l #$7bc0c,a1 (후리가나 B 블록) → 스크립트 끝 0xffff 로
    {"name": "title", "span": (0x7BC62, 0x7BC8A), "script": 0x7BC62, "immediates": [0xFFD6]},     # 0xffd4 movea.l #$7bc62,a3
    {"name": "story", "span": (0x7BF10, 0x7C204), "table": (0x7BF00, 4)},
    {"name": "briefing", "span": (0x7C224, 0x7C4C4), "table": (0x7C204, 8)},
    {"name": "king_message", "span": (0x7C4E4, 0x7C670), "table": (0x7C4C4, 8)},
    {"name": "villain", "span": (0x7C68C, 0x7CA0C), "table": (0x7C670, 7)},
    {"name": "ending", "span": (0x7CA0C, 0x7CA80), "script": 0x7CA0C, "immediates": [0x1099A]},   # 0x10998 movea.l #$7ca0c,a3
    {"name": "staff_roll", "span": (0x7CAAC, 0x7CD8E), "table": (0x7CA80, 11)},
]


DATA_REGION = (0x7B000, 0x7E200)   # 텍스트·UI 데이터 영역 (survey §5). 미등록 글리프 참조 보존 스캔 범위
FREE_SPACE = (0x7E100, 0x80000)    # 프로그램 ROM 꼬리 0xff 영역(0x7e0d0 이후). 새 코드·데이터 배치용

# 라우틴 C (0x10028~0x1004e): [오프셋 워드][ASCII 바이트…][0xfe] … [0xffff], 바이트 | d6 → 타일. 호출자 5곳.
# C2 = 같은 구조의 16비트판: [오프셋 워드][타일 워드…][0xfffe] … [0xffff]. 프로필 화면 호출자만 C2 로 돌린다.
ROUTINE_C = 0x10028
PROFILE_SETUP = (0x101BA, 0x101E4)   # move.w #$9000,d6 … jsr C … rts  (42 바이트). jmp 로 대체
C2_CODE = bytes.fromhex(
    "207c00262000"   # movea.l #$262000,a0
    "2448"           # movea.l a0,a2
    "7000"           # moveq #0,d0
    "3019"           # move.w (a1)+,d0      ; 오프셋
    "0c40ffff"       # cmpi.w #$ffff,d0
    "6714"           # beq.b rts
    "45f20000"       # lea (a2,d0.w),a2
    "7000"           # moveq #0,d0
    "3019"           # move.w (a1)+,d0      ; 타일 (원본은 move.b)
    "0c40fffe"       # cmpi.w #$fffe,d0     ; (원본은 cmpi.b #$fe)
    "67e6"           # beq.b -26 → movea.l a0,a2
    "8046"           # or.w d6,d0
    "34c0"           # move.w d0,(a2)+
    "60f0"           # bra.b -16 → moveq #0,d0
    "4e75"           # rts
)


def profile_setup_code(labels_addr: int, table_addr: int, c2_addr: int) -> bytes:
    """0x101ba 블록의 대체 루틴(빈 공간에 둔다): 라벨 → C2, 캐릭터 index(0x10301c)로 테이블 참조 → C2."""
    return (bytes.fromhex("3c3c9000") + b"\x22\x7c" + labels_addr.to_bytes(4, "big") + b"\x4e\xb9" + c2_addr.to_bytes(4, "big")
            + bytes.fromhex("3c3c6000") + b"\x22\x7c" + table_addr.to_bytes(4, "big")
            + bytes.fromhex("30390010301c" "e548" "22710000") + b"\x4e\xb9" + c2_addr.to_bytes(4, "big") + b"\x4e\x75")


def c2_encode(items: list[tuple[int, list[int]]]) -> bytes:
    """[(타일맵 바이트 오프셋, [타일 워드…]), …] → C2 데이터."""
    out = bytearray()
    for off, words in items:
        out += off.to_bytes(2, "big")
        for w in words:
            out += w.to_bytes(2, "big")
        out += b"\xff\xfe"
    out += b"\xff\xff"
    return bytes(out)


# 8×8 ASCII 타일 픽셀 규약(실측): 본체 1, 오른쪽·아래 그림자 2, 하이라이트 5. 한글 8×8 은 본체 1 + 그림자 2 로 만든다.
def hangul8_tile(mask8: list[list[int]]) -> list[list[int]]:
    t = [[0] * 8 for _ in range(8)]
    for y in range(8):
        for x in range(8):
            if mask8[y][x]:
                t[y][x] = 1
    for y in range(8):
        for x in range(8):
            if not t[y][x] and ((x > 0 and y > 0 and mask8[y - 1][x - 1]) or (x > 0 and mask8[y][x - 1]) or (y > 0 and mask8[y - 1][x])):
                t[y][x] = 2
    return t

# 2×2 글리프 띠(형식 S): 8셀×3행 워드 블록. 행1 = 각 글리프의 (k+2, k), 행2 = (k+3, k+1), 행3 = 8×8 ASCII 라벨 또는 0.
# 캐릭터 선택 화면: 직업명 4개 + 능력치 4개. 라우틴 C 류가 아니라 raw 타일맵 조각으로 복사된다(소비자 미확인, 레이아웃만 실측).
STRIP_ROW_WORDS = 8
STRIPS = [{"addr": 0x7DEBE + 48 * i, "label": ("class_name" if i < 4 else "class_stat") + f"[{i % 4}]"} for i in range(8)]


def strip_parse(img: bytes, addr: int) -> dict:
    rows = [[int.from_bytes(img[addr + r * 16 + c * 2:addr + r * 16 + c * 2 + 2], "big") for c in range(STRIP_ROW_WORDS)] for r in range(3)]
    bases, pal = [], 0
    for c in range(STRIP_ROW_WORDS):
        w = rows[0][c]
        if w and (w & 0xFFF) >= 0x200 and (w & 3) == 0:      # TR 셀 = k
            bases.append(w & 0xFFF)
            pal = w >> 12
    ascii_row = "".join(chr(w & 0x7F) if 0x20 <= (w & 0xFF) < 0x7F else "" for w in rows[2])
    ascii_pal = next((w >> 12 for w in rows[2] if w), 0)
    return {"rows": rows, "bases": bases, "pal": pal, "ascii": ascii_row, "ascii_pal": ascii_pal}


def strip_emit(bases: list[int], pal: int, ascii_row: list[int]) -> bytes:
    """글리프 base 열(≤4) 을 8셀 폭 가운데 정렬로 2행 띠로 만든다. 행3 은 그대로."""
    assert len(bases) <= STRIP_ROW_WORDS // 2
    pad = (STRIP_ROW_WORDS - len(bases) * 2) // 2
    r1 = [0] * STRIP_ROW_WORDS
    r2 = [0] * STRIP_ROW_WORDS
    for i, k in enumerate(bases):
        r1[pad + i * 2], r1[pad + i * 2 + 1] = (pal << 12) | (k + 2), (pal << 12) | k
        r2[pad + i * 2], r2[pad + i * 2 + 1] = (pal << 12) | (k + 3), (pal << 12) | (k + 1)
    return b"".join(w.to_bytes(2, "big") for w in r1 + r2 + ascii_row)


def prologue_vertical_scroll_code(step_mask: int = 3, y_stop: int = 0x1F0) -> bytes:
    """0xffac 대체 코드: (countdown & step_mask)==0 인 프레임마다 텍스트 Y+1, y_stop 에서 정지 (아래→위 크롤).
    X 는 건드리지 않는다(초기값을 0 으로 바꿔 정지 상태). 길이는 원본 루틴(0x20)에 nop 으로 맞춘다."""
    code = bytearray()
    code += b"\x30\x39\x00\x10\x30\x1c"                           # move.w $10301c.l,d0   (countdown)
    code += b"\x02\x40" + step_mask.to_bytes(2, "big")            # andi.w #mask,d0
    code += b"\x66\x10"                                           # bne.b +16 → rts
    code += b"\x0c\x79" + y_stop.to_bytes(2, "big") + b"\x00\x10\x03\x20"   # cmpi.w #y_stop,$100320.l
    code += b"\x64\x06"                                           # bcc.b +6 → rts
    code += b"\x52\x79\x00\x10\x03\x20"                           # addq.w #1,$100320.l
    code += b"\x4e\x75"                                           # rts
    size = PROLOGUE_TEXT_SCROLL_ROUTINE[1] - PROLOGUE_TEXT_SCROLL_ROUTINE[0]
    assert len(code) <= size, len(code)
    code += b"\x4e\x71" * ((size - len(code)) // 2)
    return bytes(code)
GLYPH_PX_BODY = 7      # 흰색 (팔레트 0 의 7 = 230,230,230)
GLYPH_PX_OUTLINE = 2   # 검정


def _bitswap_table() -> bytes:
    def bs(b: int) -> int:
        return (b & 0b10111101) | (((b >> 1) & 1) << 6) | (((b >> 6) & 1) << 1)
    return bytes(bs(i) for i in range(256))


BITSWAP = _bitswap_table()   # 자기 역함수 (비트 1↔6 교환)


# ---------- 프로그램 ROM ----------
def prg_decode(files: dict[str, bytes]) -> bytes:
    img = bytearray(0x80000)
    for name, base, off in PRG_FILES:
        d = files[name]
        assert len(d) == 0x20000, name
        img[base + off:base + off + 2 * len(d):2] = d
    return bytes(img).translate(BITSWAP)


def prg_encode(img: bytes) -> dict[str, bytes]:
    assert len(img) == 0x80000
    raw = img.translate(BITSWAP)
    return {name: raw[base + off:base + off + 0x40000:2] for name, base, off in PRG_FILES}


# ---------- 문자 ROM ----------
def chr_decode(region: bytes) -> list[list[list[int]]]:
    assert len(region) == 0x20000
    tiles = []
    for t in range(4096):
        px = [[0] * 8 for _ in range(8)]
        for y in range(8):
            rows = [region[PLANE_OFFS[p] + t * 8 + y] for p in range(4)]
            for x in range(8):
                bit = 7 - x
                px[y][x] = sum(((rows[p] >> bit) & 1) << (3 - p) for p in range(4))
        tiles.append(px)
    return tiles


def chr_encode(tiles: list[list[list[int]]]) -> bytes:
    region = bytearray(0x20000)
    for t, px in enumerate(tiles):
        for y in range(8):
            for p in range(4):
                v = 0
                for x in range(8):
                    v |= ((px[y][x] >> (3 - p)) & 1) << (7 - x)
                region[PLANE_OFFS[p] + t * 8 + y] = v
    return bytes(region)


def chr_split(region: bytes) -> dict[str, bytes]:
    return {"fz_02.j1": region[:0x10000], "fz_03.j2": region[0x10000:]}


def glyph_from_16x16(tiles: list[list[list[int]]], base: int) -> list[list[int]]:
    """4타일을 16×16 픽셀 행렬로 (TL=k+2, TR=k, BL=k+3, BR=k+1)."""
    out = [[0] * 16 for _ in range(16)]
    for dx, dy, tt in ((8, 0, base), (8, 8, base + 1), (0, 0, base + 2), (0, 8, base + 3)):
        t = tiles[tt]
        for y in range(8):
            for x in range(8):
                out[dy + y][dx + x] = t[y][x]
    return out


def glyph_to_16x16(tiles: list[list[list[int]]], base: int, px16: list[list[int]]) -> None:
    for dx, dy, tt in ((8, 0, base), (8, 8, base + 1), (0, 0, base + 2), (0, 8, base + 3)):
        tiles[tt] = [[px16[dy + y][dx + x] for x in range(8)] for y in range(8)]


# ---------- 스크립트 ----------
def script_parse(img: bytes, off: int) -> tuple[list[int], int]:
    """0xffff 까지의 워드 열(0xffff 제외)과 끝 오프셋(0xffff 다음)을 돌려준다."""
    words = []
    while True:
        v = int.from_bytes(img[off:off + 2], "big")
        off += 2
        if v == 0xFFFF:
            return words, off
        words.append(v)


def script_emit(words: list[int]) -> bytes:
    return b"".join(v.to_bytes(2, "big") for v in words) + b"\xff\xff"


# ---------- 폰트 시트 ----------
def hangul_sheet_glyph(sheet, ch: str, cell: int = 16) -> list[list[int]]:
    """루트 Font/ 의 *_16x16.png / *_8x8.png (유니코드 순, 64열) 에서 1비트 마스크를 꺼낸다."""
    i = ord(ch) - 0xAC00
    if not 0 <= i < 11172:
        raise KeyError(ch)
    x, y = (i % 64) * cell, (i // 64) * cell
    c = sheet.crop((x, y, x + cell, y + cell))
    return [[1 if c.getpixel((xx, yy))[1] > 127 else 0 for xx in range(cell)] for yy in range(cell)]


def mask_to_glyph(mask: list[list[int]], body: int = GLYPH_PX_BODY, outline: int | None = GLYPH_PX_OUTLINE) -> list[list[int]]:
    h, w = len(mask), len(mask[0])
    out = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                out[y][x] = body
    if outline is not None:
        for y in range(h):
            for x in range(w):
                if out[y][x]:
                    continue
                if any(0 <= y + dy < h and 0 <= x + dx < w and mask[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    out[y][x] = outline
    return out


def load_originals() -> tuple[dict[str, bytes], bytes]:
    prg = {name: (EXTRACTED / name).read_bytes() for name, _, _ in PRG_FILES}
    chr_region = b"".join((EXTRACTED / f).read_bytes() for f in CHR_FILES)
    return prg, chr_region
