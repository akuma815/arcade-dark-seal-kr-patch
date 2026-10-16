# Dark Seal 1 — PoC 기록

## PoC-1: 프롤로그 가로쓰기 한글 표시 (2026-10-04) — **PASS**

### 증명하려던 것
1. 한글 16×16 글리프(Galmuri11 11×11 + 1px 외곽선, 본체 픽셀 7·외곽 2)를 문자 ROM 의 2×2 타일 슬롯에 넣으면 게임 팔레트에서 흰 글자로 보인다.
2. 글리프 스크립트(라우틴 A)에 가로 배치 워드 열을 넣으면 코드 수정 없이 가로쓰기가 된다.
3. 부모 zip 의 ROM(fz_02/03) 을 바꾸는 패치가 FBNeo IPS 로 클론 세트(darksealj) 실행 시 적용된다.

### 방법
- 빌더 [workspace/scripts/build_poc.py](../workspace/scripts/build_poc.py) + 형식 라이브러리 [ds1lib.py](../workspace/scripts/ds1lib.py)
- 무변경 왕복(프로그램 4파일·문자 ROM 2파일 바이트 동일) → 글리프 26자를 미참조 뱅크 0xa00~0xa67 에 기록 → 스크립트 0x7ba18 을 92바이트(원본 500) 가로 워드 열로 교체 → 후리가나 쌍 블록 0x7bc0c 첫 워드 0xffff → Expected Write(선언 범위 밖 0바이트) → ROM·IPS·dat 생성 → `H:\FBNeo v1.0.0.03\support\ips\darksealj\poc.dat` 설치
- 실행: `python common\scripts\fbneo_dump.py darksealj --frames 700 --range 262000:2000 --ips poc --tag poc`

### 결과
- 화면: [evidence/poc1_screenshot.png](evidence/poc1_screenshot.png) (frame 1200) — 흰 한글 + 검은 외곽선, 4줄 가로쓰기 전부 가독. 원본 동일 프레임: [evidence/prologue_original_f1200.png](evidence/prologue_original_f1200.png).
- **주의: 프롤로그 텍스트 레이어는 어트랙트 시작 후 가로로 슬라이드해 들어온다.** frame 700 캡처에선 왼쪽 8셀이 아직 화면 밖이라 잘린 것처럼 보였다(스크롤 레지스터 0x240000 은 쓰기 전용이라 Lua 로 못 읽음). 판정 프레임은 1200 이상으로 잡는다.
- 텍스트 레이어 덤프: 타일 0xa00~0xa67 이 행 2~5·8~11, 열 2~25 에 가로 배치(2줄 + 빈 줄 + 2줄). 일본어 글리프·후리가나 잔재 없음.
- 변경 ROM: `fz_00-2.h12`, `fz_05-2.j14`(스크립트), `fz_02.j1`, `fz_03.j2`(글리프). IPS 4개.

### 사후 정정 (2026-10-04)
- 위 "슬라이드" 설명은 절반만 맞았다. 프레임별 캡처([evidence/poc1_horizontal_slide_sheet.png](evidence/poc1_horizontal_slide_sheet.png))로 확인한 실제 연출: **텍스트 레이어가 왼쪽에서 오른쪽으로 0.25px/프레임 슬라이드해 들어와 정지**한다(세로쓰기 열에 맞춘 연출). 가로쓰기 한글에는 어색 → PoC-2 로 세로 크롤로 변경.

## PoC-2: 프롤로그 아래→위 크롤 (2026-10-04) — **PASS**

### 근거 (코드)
- 레이어↔스크롤 변수: 텍스트 레이어 pf_ram[1](0x262000)=칩0 pf2 → 제어 0x2a0006/8 ← RAM **0x10031c(X)/0x100320(Y)**. 빨간 배경 pf_ram[3](0x202000)=칩1 → 0x240006/8 ← 0x10038c/0x100390. (처음엔 후자를 텍스트로 오인해 배경이 세로로 움직였음 — 교정.)
- 프롤로그 설정 0xff54: 텍스트 X=0x100, Y=0. 프레임 루프(0xfe82~0xfee0)가 매 프레임 0xffac 호출: `countdown&3==0` 마다 X-1 → 0 에서 정지 = 슬라이드 인.
- 월드판(영문 가로쓰기)도 같은 구조로 옆에서 들어온다([evidence/../work/scroll_trace/world_f1500.png] 참고).

### 패치 (ds1lib.prologue_vertical_scroll_code, build_poc.py)
| 위치 | 변경 |
| --- | --- |
| 0xffac~0xffcb (0x20B) | `countdown&3==0` 마다 `Y(0x100320)+1`, `Y>=0x1f0` 이면 정지. 나머지 nop |
| 0xff6a (2B) | 텍스트 X 초기값 0x100 → 0 (정지 위치) |
| 0xff8e (4B) | 스크립트 시작 a2 = 0x262100(2행) → 0x262f00(30행 = 화면 아래 가장자리) |

### 결과
[evidence/poc2_vertical_crawl_sheet.png](evidence/poc2_vertical_crawl_sheet.png): 500f 하단 등장 → 1000f 거의 상단 → **1300f 첫 줄이 y=16 에 닿아 정지, 이후 유지** (사용자 결정: 월드판처럼 다 올라온 뒤 멈춤). 배경 정지. 속도 0.25px/f, 정지값 Y=224 (`--y-stop` 기본). 본문은 14줄(224px) 이하여야 하며 빌더가 초과 시 실패한다.
- 프롤로그 **전문 초벌**(12줄 + 빈 줄 2 = 14줄, 글리프 69자 → 타일 0xa00~0xb13, 스크립트 334/500B)로 재검증: [evidence/poc2_full_prologue_sheet.png](evidence/poc2_full_prologue_sheet.png) — 700f 하단 등장 → 1100f 전체 표시·정지 → 2100f 유지. 괄호 글리프 `( )` 는 수제 마스크(build_poc.PUNCT).
- 관찰: 16px 셀에 11px 글리프라 자간이 넓어 보인다. 글리프 라이터가 2타일 고정 피치이므로 자간을 줄이려면 라이터 훅(가변 피치) 또는 12px 폰트 검토 — 번역 원장 단계에서 사람이 결정.

### 한계·주의
- 뱅크 0xa00~0xfff 는 "스크립트 미참조"일 뿐 다른 소비자(게임 중 그래픽) 여부 미확인 → 배포 설계에서는 사용 글리프 슬롯을 소비자 조사 후 확정한다.
- 창 캡처는 `fbneo_lua.capture_window`(PrintWindow + DPI aware, Lua 콘솔 자동 닫기)로 전체 클라이언트(960×752)를 받는다.
- PoC 문구는 초벌(검토 전)이며 번역 원장이 아니다.
