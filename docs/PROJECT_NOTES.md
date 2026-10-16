# Dark Seal 1·2 (Arcade, Data East) 한글화

- 플랫폼 / 지역: 아케이드 / 일본판 2종. 에뮬레이터는 **FBNeo v1.0.0.03** (`H:\FBNeo v1.0.0.03`)
- 현재 단계: **1편 초벌 빌드(`-ips kr`) 어트랙트 QA PASS, 사람 검토 대기 / 2편 PoC PASS → 추출기 단계** ([darksealj/docs/build.md](darksealj/docs/build.md)) ([darksealj/docs/survey.md](darksealj/docs/survey.md) · [darksealj/docs/poc.md](darksealj/docs/poc.md) · [darkseal2/docs/survey.md](darkseal2/docs/survey.md) · [darkseal2/docs/poc.md](darkseal2/docs/poc.md))
- 작업 폰트: 본문 16×16 `Font/Galmuri11_16x16.png`, 8×8 자리 `Font/Galmuri7_8x8.png` (둘 다 유니코드 순 64열 시트, OFL)
- 검증·배포 경로: FBNeo IPS (`support/ips/<세트>/<name>.dat` + `fbneo64.exe <세트> -ips <name>`)
- 진입점: 작업을 이어받을 때는 **[docs/HANDOFF.md](docs/HANDOFF.md)를 먼저 읽는다.** 작업이 끝날 때마다 반드시 갱신한다.
- 방법론: 루트 `신규_게임_한글화_구조_가이드.md` 4장 표준 구조 + `create-kr-patch` 스킬

## 두 게임, 두 하드웨어

| 폴더 | 게임 | FBNeo 세트 (dat 확인) | 드라이버 (dat 확인) | 원본 zip |
| --- | --- | --- | --- | --- |
| `darksealj/` | Dark Seal (Japan revision 4, 1990) | `darksealj` ← 부모 `darkseal` | `dataeast/d_darkseal.cpp` | `original/darksealj.zip` + `darkseal.zip` |
| `darkseal2/` | Dark Seal 2 (Japan v2.1, 1992) = Wizard Fire 일본판 | `darkseal2` ← 부모 `wizdfire` (MAME 명은 `darksel2`) | `dataeast/d_rohga.cpp` | `original/darkseal2.zip` + `wizdfire.zip` |

같은 시리즈지만 **그래픽 하드웨어·드라이버가 다르다** (1편 Dark Seal 전용 보드, 2편 Rohga 계열 보드). 텍스트 형식, 폰트 타일 규격, 포인터 규칙을 1편에서 2편으로 그대로 가정하지 않는다. 용어·캐릭터명 등 번역 자산만 `common/glossary/`로 공유한다. CPU 종류는 아직 소스로 확인하지 않았다(둘 다 68000 계열로 추정).

## 부팅 확인 (2026-10-04)

| 게임 | 명령 | 결과 |
| --- | --- | --- |
| 1편 | `fbneo64.exe darksealj -w` | 부팅. 어트랙트 첫 화면이 **세로쓰기 일본어 프롤로그**(한자+후리가나) — `darksealj/work/boot_fbneo_darksealj*.png` |
| 2편 | `fbneo64.exe darkseal2 -w` | 부팅. 어트랙트 첫 화면이 **가로쓰기 일본어 프롤로그**(한자, 타자기 효과) — `darkseal2/work/boot_fbneo_darkseal2_*.png` |

두 게임 모두 **한자를 포함한 일본어 본문이 존재**한다. 즉 단순 영문 HUD 번역이 아니라 한자 폰트(2×2 타일 추정)를 한글로 바꾸는 작업이며, 그 폰트가 **부모 세트의 GFX ROM**에 있다면 패치가 부모 zip까지 미친다. 이것이 조사 1순위다.

## 원본·전개

- `original/` 6개 zip. 해시·dat 대조 결과는 [original/README.md](original/README.md). FBNeo dat 발췌 원문은 [docs/fbneo_sets.xml](docs/fbneo_sets.xml).
- 작업용 4세트(클론 2 + 부모 2)는 `python common/scripts/extract_sets.py` 로 `<게임>/extracted/`(클론) · `<게임>/extracted/parent/`(부모)에 전개된다. `darkseal1.zip`, `wizdfirea.zip` 은 보관만 한다.
- FBNeo 의 rompath `roms/arcade/` 에 같은 9개 세트가 이미 있고 SHA-256 이 `original/` 과 동일하다. **FBNeo 쪽 zip 을 직접 고치지 않는다** — 패치 빌드는 `build/` 에 만들고 별도 경로나 IPS 로 공급한다.

## 환경

| 항목 | 상태 |
| --- | --- |
| FBNeo v1.0.0.03 | `H:\FBNeo v1.0.0.03\fbneo64.exe` (+ 디버그 빌드 `fbneo64d.exe`). 상세는 [tools/README.md](tools/README.md) |
| FBNeo Lua | Lua 5.1.4, FBA-rr 계열 API (`memory.read/write*`, `memory.registerexec/read/write`, `emu.frameadvance/registerafter`, `gui.text`, `savestate`, `joypad`). 메뉴 Misc → Lua Scripting |
| FBNeo IPS | `support/ips/<세트명>/*.ips` + IPS Manager — 배포 후보 경로 |
| Python | 3.12.10 |
| 공용 폰트 | 루트 `Font/` (Galmuri, neodgm, DungGeunMo 등) |
| xdelta3 | 루트 `Tools/xdelta3-3.2.0-windows-x86_64` |

## 폴더 매핑

```text
Dark Seal/
├─ README.md                 # 이 문서
├─ docs/                     # 두 게임 공통 기록. HANDOFF.md(인계), fbneo_sets.xml(dat 근거)
├─ original/                 # 사용자 소유 원본 zip. 어떤 스크립트도 여기에 쓰지 않는다
├─ common/
│  ├─ scripts/               # 두 게임 공용 도구 (extract_sets.py 등)
│  ├─ font/                  # 공용 폰트 가공 중간물
│  └─ glossary/              # 시리즈 공용 용어·캐릭터명 SSOT
├─ tools/                    # 외부 도구 기록 (FBNeo 경로·버전·Lua/IPS 사용법)
├─ darksealj/                # 1편 — 아래 표준 구조
└─ darkseal2/                # 2편 — 아래 표준 구조
   ├─ docs/                  # survey / format / build / qa / decisions
   ├─ extracted/             # 클론 ROM + rom_info.json / parent/ 부모 ROM (재생성 가능)
   ├─ workspace/
   │  ├─ scripts/ config/ tests/
   │  ├─ text/{source,translation,reports}/   # translation = 사람이 고치는 SSOT
   │  ├─ font/{source,mapping,generated}/
   │  └─ graphics/{source,translated}/
   ├─ work/                  # 언제든 삭제·재생성 (부팅 스크린샷 등)
   ├─ build/                 # 패치 적용된 ROM 세트 (재생성 가능)
   └─ dist/                  # 배포물만: 패치·SHA-256·적용법
```

## 명령

| 목적 | 명령 (프로젝트 루트에서) |
| --- | --- |
| 원본 → extracted 전개·해시 매니페스트 | `python common/scripts/extract_sets.py` |
| 1편 / 2편 창모드 실행 | `& "H:\FBNeo v1.0.0.03\fbneo64.exe" darksealj -w` / `… darkseal2 -w` (작업 디렉터리를 FBNeo 폴더로) |
| 단일 빌드 | (미작성) |

## 번역 범위 (잠정)

프롤로그 본문(두 게임 모두 확인) + 타이틀·HUD·캐릭터 선택·스테이지 인트로·엔딩·크레딧. **실제 분모는 조사 단계에서 소비자 경로별로 확정**하며, 로고·이미지 텍스트 여부는 별도 카탈로그로 구분한다. 1편 세로쓰기 프롤로그를 한글 세로쓰기로 유지할지 가로로 재배치할지는 사람이 결정한다.

## 알려진 문제

- 조사 전: 텍스트 인코딩·폰트 위치·CPU 모두 미확인
- FBNeo 는 MAME 식 대화형 디버거가 없다. 추적은 Lua `memory.registerexec/registerwrite` 로 한다. 부족하면 MAME 병행을 검토한다
