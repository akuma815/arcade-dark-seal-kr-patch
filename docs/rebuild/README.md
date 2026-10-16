# 최종 FBNeo IPS 재빌드

이 저장소는 `darksealj`과 부모 `darkseal`를 대상으로 합니다. 필요한 원문 블록·글리프 매핑 JSON, 승인된 번역 원장과 Galmuri 폰트를 포함했습니다. 과거 추출·QA 폴더나 비공개 복원 ZIP 없이 **Git 소스와 별도 원본 ROM ZIP 2개**로 최종 IPS를 다시 만듭니다.

## 실행

Python 3.12에서 저장소 최상위에서 실행합니다.

```powershell
python -m pip install -r requirements-rebuild.txt
python -X utf8 -B scripts/rebuild_final.py --clone-zip "darksealj.zip의 절대 경로" --parent-zip "darkseal.zip의 절대 경로" --output-dir build/restored_final
```

출력 폴더는 아직 존재하지 않는 새 경로를 사용하세요. 원본 ZIP은 수정하지 않습니다. 각 ZIP의 내부 ROM 이름·크기·CRC32·SHA-256을 모두 확인하므로 ZIP을 다시 압축해도 내부 ROM이 같으면 사용할 수 있습니다. 지원 리비전 및 공개 입력 해시는 [INPUTS.json](INPUTS.json)에 있습니다. 다른 게임이나 다른 지역·리비전은 거부합니다.

결과 IPS 6개와 `Korean.dat`는 출력 폴더 안의 `project/darksealj/build/Korean/`에 생성됩니다. `REBUILD_RESULT.json`에는 최종 릴리즈 IPS 해시 일치와 실제 IPS 적용 결과를 기록합니다. 이 폴더에는 검증용 원본 추출본·수정 ROM도 있으므로 공개 업로드하지 마세요. 배포에는 IPS·DAT만 사용합니다.

## 승인 원장과 동결된 입력

사용자가 직접 수정·승인한 번역 원장을 그대로 사용합니다. **`apply_drafts.py`는 실행하지 않습니다.** 빌더는 `--name Korean --min-status approved --no-install`로 실행해 에뮬레이터 설치 폴더를 바꾸지 않습니다. 원본 ROM에서 무변경 왕복과 Expected Write 검사를 수행하고 패치를 만듭니다.

폰트는 [외부 자료 안내](../../THIRD_PARTY_NOTICES.md)의 Galmuri 파일을 저장소에 포함했습니다. 입력 해시가 달라지면 최종판 재현 명령은 중단합니다. 새 문안은 해당 게임의 `workspace/text/translation` 원장에서 수정하고, 해당 버전의 블록·글리프 맵과 하위 빌더로 별도 출력 경로에서 작업하세요. 새 입력의 결과는 기존 최종 릴리즈와 별도로 검증해야 합니다.

## 검증 범위

실제 재빌드와 다운로드한 GitHub 릴리즈 비교는 [VERIFICATION_2026-10-16.json](VERIFICATION_2026-10-16.json)을 참고하세요. 릴리즈 ZIP의 해시·CRC, IPS 6개의 해시, DAT 바이트와 IPS 적용 결과를 대조했습니다. 원본 ROM ZIP·수정 ROM·BIOS는 저장소에 포함하지 않습니다. 이번 작업에서는 새 에뮬레이터 실행·장면 검수·전체 플레이 검수를 수행하지 않았습니다.

과거 세이브·실행 덤프·중간 후보 전체는 공개 복원 범위에 포함하지 않습니다. 패치 설치·사용은 저장소 README와 릴리즈 안내를 따르세요.
