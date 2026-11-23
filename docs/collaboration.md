# 협업 규칙: 충돌 없이 같이 개발하기

[TEAM_README.md](../TEAM_README.md)의 Git 규칙(브랜치 → PR → squash merge)에 더해, **충돌을 미리 막는 규칙**과 **충돌이 났을 때의 절차**를 정리한다.

## 1. 작업 한 사이클

```bash
# ① 시작: 항상 최신 main에서 브랜치를 딴다
git checkout main && git pull
git checkout -b feat/기능이름

# ② 작업 중: 하루 한 번 이상, 그리고 PR 직전에 반드시
bash scripts/sync_check.sh        # 충돌 예상 파일 + 팀원 브랜치와 겹치는 파일
git merge origin/main             # 뒤처졌으면 최신 main 반영 (rebase 대신 merge: 공유 브랜치 이력을 바꾸지 않는다)
python -m pytest tests -q         # 합친 뒤에도 통과하는지

# ③ 기록: docs/devlog/ 에 이번 작업 파일 1개 추가 (아래 4절)

# ④ PR: 작은 단위로 자주. 오래 열어 둔 PR일수록 충돌이 커진다
git push -u origin feat/기능이름
```

`sync_check.sh`는 작업 트리를 바꾸지 않는다(`git merge-tree`로 가상 병합만 한다). 종료 코드 1이면 충돌이 예상된다는 뜻이다.

## 2. 충돌을 미리 막는 규칙

| 규칙 | 이유 |
|---|---|
| **작업 시작 전에 팀 채팅에 "브랜치 이름 + 고칠 파일"을 남긴다** | 같은 파일을 동시에 고치는 것을 사람이 먼저 알아챈다. 아래 3절 표에 적어도 된다 |
| **새 기능은 새 모듈 파일에 둔다** | `aggregator.py`, `main.py`, `app.py`는 모두가 고치는 파일이다. 새 분석은 `spike.py`처럼 별도 모듈에 두고, 공유 파일에는 호출 몇 줄만 추가한다 ([ADR-001](decisions/ADR-001-feature-modules.md)) |
| **공유 파일을 고칠 때는 끝에 추가한다** | 함수·상수·출력 파일 이름은 기존 줄 사이가 아니라 해당 구역 끝에 붙인다. 두 사람이 서로 다른 위치를 고치면 git이 자동 병합한다 |
| **포맷터·정렬·이름 변경은 단독 PR로 뺀다** | 파일 전체를 건드리는 변경이 기능 PR에 섞이면 모든 PR과 충돌한다 |
| **줄바꿈은 `.gitattributes`가 LF로 통일한다** | Windows와 macOS가 섞여도 줄바꿈 차이로 파일 전체가 충돌하지 않는다 |
| **기록 문서는 파일을 나눈다** | 작업 기록은 `docs/devlog/`에 작업마다 새 파일로 쓴다. 한 파일 끝에 계속 추가하면 PR마다 충돌한다 |

### 충돌이 잘 나는 파일 (hotspot)

| 파일 | 자주 바뀌는 곳 | 충돌 줄이는 법 |
|---|---|---|
| `app.py` | `app.layout`, `update()` 콜백 `Output`, `build_view()` 반환 | 화면 요소는 layout 맨 아래에 추가하고, Output도 맨 뒤에 추가 |
| `main.py` | `OUT_*` 상수, `run()` 본문 | 상수와 호출을 각 구역 끝에 추가 |
| `config.py` / `config.json` | `Settings` 필드 | 필드를 클래스 맨 끝에 추가 |
| `README.md` | 출력 파일 표, 설정 항목 표 | 표 맨 아래 행에 추가 |
| `AI_USAGE.md` | 기능별 기록 표 | 표 끝에 행 추가. 충돌하면 두 행을 모두 남기면 된다 |

## 3. 진행 중인 작업 (누가 무엇을)

PR을 열 때 이 표를 고치지 말고 팀 채팅이나 PR 설명에 적는 것을 권장한다. 이 표는 큰 단위 역할 분담만 적는다.

| 작업 | 담당 | 브랜치 | 주로 고치는 파일 |
|---|---|---|---|
| O2 불량 급증 탐지 | jangjunseo05 | `feat/spike-detection` | `spike.py`(신규), `main.py`, `app.py`, `config.py` |
| O1 불량 박스 분석 | (미정) | | |
| D99 제외 불량률 옵션 | (미정) | | |
| 한글 글꼴 동봉 | (미정) | | |

## 4. 작업 기록 (docs/devlog)

작업(PR) 하나마다 `docs/devlog/YYYY-MM-DD-주제.md` 파일을 하나 만든다. 양식은 [devlog/_template.md](devlog/_template.md)를 복사해 쓴다. 나중에 포트폴리오를 쓸 때 "문제 → 판단 → 결과 → 수치" 재료가 된다.

## 5. 충돌이 났을 때

`.claude/skills/fix-merge-conflicts` 스킬의 절차를 따른다. 요약:

1. **내 브랜치에서** 해결한다. `main`이나 팀원 브랜치에서 해결하지 않는다.
2. `git fetch origin && git merge origin/main`으로 충돌을 실제로 재현한다.
3. 충돌 파일마다 `git log --merge -p -- <파일>`로 **양쪽이 왜 그렇게 바꿨는지** 커밋 메시지를 읽는다.
4. 기본은 **양쪽 의도를 모두 살리는 것**이다. "내 것/상대 것 통째로 선택"은 하지 않는다. 정말 양립할 수 없으면 main 쪽 의도를 따르고 내 코드를 맞춘 뒤 PR 설명에 적는다.
5. `python -m pytest tests -q`와 `python main.py`를 다시 돌린다. 테스트가 깨지면 어딘가 잘못 고른 것이다.
6. 커밋 메시지에 두 의도를 적는다. 예: `merge: main의 O1 박스 집계 + 이 브랜치의 급증 탐지 출력 둘 다 유지`
7. **공유 브랜치에 force-push 하지 않는다.**

### 쌓은 브랜치(stacked)를 squash merge 한 뒤의 충돌
B 브랜치를 A 브랜치 위에 쌓고 A를 squash merge 하면, main에는 A의 내용이 **새 커밋 하나**로 들어간다. B 입장에서는 같은 변경이 다른 커밋으로 양쪽에 있게 되어, 둘 다 새로 만든 파일을 B가 더 고쳤다면 `CONFLICT (add/add)`가 난다.

- 해결: B에서 `git merge origin/main` 후 충돌 파일을 `git diff origin/main HEAD -- <파일>`로 비교한다. B 쪽이 main 쪽 내용을 모두 포함하고 추가만 했다면 B 쪽이 두 의도를 모두 담은 결과다.
- 예방: 가능하면 쌓지 말고 main에서 바로 브랜치를 딴다. 쌓아야 하면 A가 머지된 직후 바로 B에 main을 merge 한다.
- 실제 사례: [devlog/2026-11-23-spike-detection.md](devlog/2026-11-23-spike-detection.md)의 협업 메모

## 6. AI(Claude Code)와 함께 작업할 때 쓰는 스킬

`.claude/skills/`에 있는 스킬은 [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)(MIT)에서 내용을 읽어 확인한 뒤 가져왔다.

| 스킬 | 언제 |
|---|---|
| `execute` | 합의된 작업을 구현할 때. 작은 단위로 구현하고 검증까지 |
| `minimal-code-discipline` | diff를 작게 유지할 때. 작은 diff가 곧 적은 충돌이다 |
| `tdd` | 집계 함수처럼 기대값을 손으로 정할 수 있는 기능 |
| `blast-radius` | 집계 함수 시그니처나 `Settings`처럼 여러 파일이 쓰는 것을 바꿀 때. 영향받는 곳을 찾고 테스트로 확인 |
| `fix-merge-conflicts` | 충돌 해결 (5절) |
| `review` / `verify` | PR 전 자체 검토와 동작 검증 |
| `technical-writing` | README, devlog, 포트폴리오 문서 작성 |
| `what-did-i-get-done` | 일정 기간 내 커밋을 주제별로 요약. 주간 보고·포트폴리오 정리용 |
