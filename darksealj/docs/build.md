# Dark Seal 1 — 빌드·검증 절차 (2026-10-04 기준)

## 파이프라인

```text
original/*.zip
  └─ common/scripts/extract_sets.py        → extracted/ (클론) + extracted/parent/ (부모)
workspace/scripts/extract_text.py          → text/source/ds1_blocks.json   (A 스크립트 42, S 띠 8, B/C 블록)
workspace/scripts/glyph_map.py seed|sheet|fill|decode
                                           → font/mapping/ds1_glyph_map.json (374 글리프↔문자), text/source/ds1_text_ja.json
workspace/scripts/make_ledger.py           → text/translation/ds1_translation.json (SSOT, 44 항목)
workspace/scripts/apply_drafts.py drafts_*.json   → 원장에 ko_rows/status 반영 + 폭·줄 수·글리프 공급 검사
workspace/scripts/build_translation.py     → build/kr/ (ROM 6 + IPS 6 + kr.dat + report.json) → FBNeo support/ips/darksealj/
common/scripts/fbneo_dump.py darksealj --ips kr --frames … → work/dumps_*/screenshot_<frame>.png (QA)
```

## build_translation.py 가 하는 일

1. 무변경 왕복(프로그램·문자 ROM) 바이트 동일 검사.
2. **글리프 배정**: 번역문 문자 → (a) 원문 글리프 표에 있는 문장부호(、。“”！‼‥)는 기존 타일 재사용, (b) 한글·수제 부호(, . ( ) ? !)는 새 타일. 새 타일 슬롯 = 번역된 A/S 가 쓰던 일본어 글리프 중 **보존 집합에 없는 것** → 부족분은 0xa00~0xfff.
   보존 집합 = 미번역 A/S 의 글리프 + 재사용 문장부호 + **데이터 영역(0x7b000~0x7e200)에서 등록 블록 밖에 보이는 글리프형 워드 전부**(미등록 소비자 대비; 1차 빌드에서 캐릭터 선택 띠가 깨진 사고의 재발 방지).
3. **아레나 재배치**: 같은 포인터 테이블/즉시값이 가리키는 연속 영역(ds1lib.SCRIPT_ARENAS 8개) 안에서 번역 스크립트를 순서대로 다시 깔고 테이블·즉시값을 갱신. 블록별 원본 크기 제한이 사라지고 아레나 합계만 지키면 된다. 미번역 스크립트는 원본 바이트를 그대로 이동. 남는 공간 0xff.
4. 띠(S) 방출: 8셀 폭 가운데 정렬 2행, 행3(8×8 영문 라벨)은 유지.
5. 프롤로그: 세로 크롤 패치(0xffac 루틴, X 초기값, 시작 행 30) + 후리가나 B 블록 호출자를 스크립트 끝 0xffff 로.
6. **프로필 화면(C→C2)**: 라우틴 C(0x10028, 1바이트=1타일 ASCII)는 한글 타일(0x100 이상)을 못 가리키므로 16비트판 C2 를 ROM 꼬리 빈 공간(0x7e100~, 원본 0xff)에 두고, 프로필 설정 블록 0x101ba~0x101e4 를 `jmp` 로 새 설정 루틴에 넘긴다(라벨/값 데이터·테이블도 빈 공간). 다른 C 호출자 3곳(0x10b1c·0x10cbc·0x10cca)은 원본 유지. 8×8 한글은 Galmuri7(본체 1·그림자 2) 을 문자 ROM 꼭대기 0xfff 부터 아래로 배정(16×16 배정과 충돌 검사).
7. Expected Write(선언 범위 밖 변경 0바이트) → IPS 생성·설치.

## 현재 빌드 수치 (kr, 2026-10-04)

- 번역 36/49: 본문 22 + 띠 8 + 프로필 5 = **35 approved(2026-10-04 사용자 승인)**, 계급명 1 draft. 미번역: 스태프롤 11(**사용자 결정: 일본어 유지**), 빈 항목 2.
- 계급명 블록(0x7e03e, 8셀 필드×9, 팔레트 9)은 16비트 타일 워드라 코드 수정 없이 8×8 한글 타일을 직접 넣는다(가운데 정렬).
- 글리프: 16×16 재사용 4 + 신규 234 (해제 슬롯 141 + 0xa00~ 93), 보존 266. 8×8 한글 89타일(0xfa7~0xfff). 빈 공간 754B 사용.
- 변경 ROM: 프로그램 4(스크립트·포인터·크롤 코드·C2·훅), 문자 ROM 2. 모두 IPS 로 배포 가능.

## QA 기록

| 빌드 | 결과 | 증거 |
| --- | --- | --- |
| kr #0 | 프롤로그·스토리·브리핑 OK, **캐릭터 선택 띠 깨짐**(해제 슬롯이 미등록 소비자와 충돌) | [evidence/kr_build0_strip_corruption_sheet.png](evidence/kr_build0_strip_corruption_sheet.png) |
| kr #1 | 띠 번역 + 보존 집합 확장 후 전부 OK (프롤로그·스토리·캐릭터 선택·브리핑·데모 HUD) | [evidence/kr_build1_attract_sheet.png](evidence/kr_build1_attract_sheet.png) |
| kr #2 | 프로필 화면 한글(8×8) OK, 하이스코어 화면 직업명 띠 OK, 경고 화면·HUD 영문 그대로 | [evidence/kr_build2_profile_sheet.png](evidence/kr_build2_profile_sheet.png) |
| kr #3 | 계급명(하이스코어 "종자") 8×8 한글, 8셀 필드 가운데 정렬 OK | [evidence/kr_build3_ranks_sheet.png](evidence/kr_build3_ranks_sheet.png) |

미검증: 게임 중 메시지(왕의 메시지·악역 대사·엔딩 — 실제 진행 필요), 0xa00~0xfff 뱅크의 미지 소비자. FBNeo `bAutoPause` 는 자동 QA 를 위해 0 으로 바꿔 두었다(tools/README.md).
