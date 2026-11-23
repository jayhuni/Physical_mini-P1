# 2026-11-23 협업 환경 구성

- 작성자: jangjunseo05 (Claude Code와 작업)
- 브랜치 / PR: `chore/collab-setup`
- 관련 요구사항: 고도화 준비 (O1, O2 병행 개발)

## 문제
과제 제출 이후 팀원과 O1(박스 분석), O2(급증 탐지)를 동시에 개발한다. 기존 구조에서는 새 집계가 모두 `aggregator.py`에 모이고, 화면 추가는 `app.py`의 같은 layout·콜백을 고치게 되어 두 PR이 거의 확실히 충돌한다. 또한 팀원의 OS가 다르면 줄바꿈 차이만으로 파일 전체가 충돌할 수 있었다(이 PC는 `autocrlf=true`로 작업 트리가 CRLF였다).

## 판단
- **충돌을 사후에 해결하기보다 사전에 감지한다.** `git merge-tree --write-tree`(Git 2.38+)는 작업 트리를 건드리지 않고 가상 병합을 해 충돌 파일을 알려 준다. 이를 스크립트로 만들어 PR 전에 돌리게 했다.
- **팀원의 진행 중 브랜치와 겹치는 파일도 경보한다.** main과 충돌이 없어도, 아직 병합되지 않은 팀원 브랜치와 같은 파일을 고치고 있으면 나중에 충돌한다. 원격 브랜치마다 변경 파일을 비교한다.
- **구조로 충돌 면적을 줄인다.** 새 기능은 별도 모듈에 둔다([ADR-001](../decisions/ADR-001-feature-modules.md)). 기록 문서는 한 파일에 계속 추가하지 않고 작업마다 새 파일을 만든다.
- 버린 방법: 브랜치 보호·CI 설정. `gh` CLI가 없고 저장소 권한 설정이 필요해 보류했다. 추후 GitHub Actions로 `pytest`와 `sync_check`를 PR마다 돌리는 것을 검토한다.

## 한 일
- `scripts/sync_check.sh`: 뒤처진 커밋 수, main과의 충돌 예상 파일, 팀원 브랜치와 겹치는 파일 출력. 충돌 예상 시 종료 코드 1
- `.gitattributes`: 저장소 줄바꿈을 LF로 통일. 저장소 인덱스가 이미 LF라 기존 파일은 바뀌지 않는다
- `docs/collaboration.md`: 작업 사이클, 충돌 예방 규칙, hotspot 파일, 충돌 해결 절차, 스킬 사용 시점
- `.github/pull_request_template.md`: 테스트·충돌 점검·기록 체크리스트
- `CLAUDE.md`: Claude Code가 작업 시작·종료 시 지킬 규칙 (팀원도 Claude Code를 쓰면 같은 규칙이 적용된다)
- oh-my-claudecode 스킬 5개 추가: `execute`, `minimal-code-discipline`, `blast-radius`, `fix-merge-conflicts`, `what-did-i-get-done`. 내용을 읽고 수정 없이 복사했다

## 검증
- 임시 저장소(bare origin + 클론 2개)로 시나리오를 재현했다. main에 `app.py` 변경을 push하고, 팀원 브랜치에 `config.py` 변경을 push한 뒤, 내 브랜치에서 두 파일을 모두 고쳤다.
  - 결과: `! app.py` 충돌 예상, `origin/feat/teammate 와 겹침: config.py`, 종료 코드 1. 의도대로 동작했다
- 실제 저장소에서 실행: 충돌 없음, 겹침 없음, 종료 코드 0
- 기존 테스트: 34 passed, 4 skipped (`input/` 데이터가 없는 PC라 통합 테스트 4개가 건너뛰어짐)

## 협업 메모
- TEAM_README 규칙 1의 문구를 바꿨다. 팀원에게 ADR-001 합의를 받아야 한다.

## 포트폴리오 포인트
- 2인 병행 개발에서 충돌을 사후 해결이 아니라 **사전 감지**하도록 `git merge-tree` 기반 점검 스크립트를 만들고, 기능별 모듈 분리·문서 파일 분리·줄바꿈 통일로 **충돌이 날 수 있는 면적 자체를 줄였다**.
