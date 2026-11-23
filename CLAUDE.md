# CLAUDE.md

이 저장소에서 Claude Code가 지킬 규칙. 사람용 설명은 [TEAM_README.md](TEAM_README.md), 협업 규칙은 [docs/collaboration.md](docs/collaboration.md).

## 작업 시작 전
- `bash scripts/sync_check.sh`를 실행해 origin/main과의 충돌 예상 파일과 팀원 브랜치와 겹치는 파일을 확인하고 사용자에게 알린다.
- `main`에서 직접 작업하지 않는다. 최신 `main`에서 `feat/`, `fix/`, `docs/`, `chore/` 브랜치를 딴다.

## 코드 규칙 (TEAM_README 3절 요약)
- `app.py`에 `groupby`, `pivot_table`, `value_counts` 등 집계 코드를 쓰지 않는다. 집계는 `aggregator.py` 또는 기능별 분석 모듈(`spike.py` 등)에 둔다.
- 파일 이름, 폴더, 기준값은 `config.Settings`와 `config.json`에 둔다.
- 파일 입출력은 인코딩을 명시하고, CSV 저장은 `exporter.save_csv`를 쓴다.
- 주석은 한글로, "왜"가 드러나게 쓴다.
- 공유 파일(`app.py`, `main.py`, `config.py`, `README.md`)은 구역 끝에 추가하는 방식으로 고쳐 충돌을 줄인다. 포맷 변경을 기능 변경에 섞지 않는다.
- 테스트 기대값은 구현이 아니라 손으로 계산한 값으로 정한다.

## 작업 끝낼 때
- `python -m pytest tests -q`를 실행하고 결과(passed/skipped 수)를 그대로 보고한다. `input/` 데이터가 없으면 skipped가 생긴다는 점을 함께 알린다.
- `docs/devlog/YYYY-MM-DD-주제.md`에 작업 기록을 새 파일로 추가한다(`docs/devlog/_template.md` 양식).
- 설계 판단이 있었으면 `docs/decisions/ADR-NNN-*.md`로 남긴다.
- PR 전에 `bash scripts/sync_check.sh`를 다시 돌리고, 뒤처졌으면 `git merge origin/main` 후 테스트를 다시 돌린다.
- 충돌 해결은 `.claude/skills/fix-merge-conflicts` 절차를 따른다. 공유 브랜치에 force-push 하지 않는다.
- push와 PR 생성은 사용자 확인 후에 한다.
