# 팀원 가이드: 이 프로젝트를 이어서 개발하려면

이 문서를 읽으면 프로젝트를 내려받아 실행하고, 코드 구조를 파악하고, 기능을 추가해 PR로 올릴 수 있다. 프로그램 사용법은 [README.md](README.md), 과제 명세는 [비전검사_로그_통합_처리_프로그램_개발.md](비전검사_로그_통합_처리_프로그램_개발.md)에 있다.

## 1. 10분 안에 실행해 보기

```bash
git clone https://github.com/jayhuni/Physical_mini-P1.git
cd Physical_mini-P1
pip install -r requirements.txt
```

제공 데이터는 저장소에 없다. 프로젝트 폴더에 `input/` 폴더를 만들고 `facility_A_log.csv`, `facility_B_log.csv`, `facility_C_log.csv`, `defect_codes.csv`를 넣는다. 데이터는 팀 내에서 따로 전달받는다.

```bash
python -m pytest tests -q   # 38 passed, skipped 0 이면 정상
python main.py              # 전체 처리. 결과는 output/ 에 생성
python app.py               # 대시보드. http://127.0.0.1:8050
```

`pytest` 결과에 skipped가 있으면 `input/`에 데이터가 없다는 뜻이다. 통합 테스트가 실행되지 않은 상태이므로 데이터를 넣고 다시 돌린다.

## 2. 구조를 한눈에

```
input/*.csv ──> loader ──> aggregator ──┬──> main.py ──> output/ (CSV, PNG, summary.txt)
                 (읽기·병합)  (집계·필터)   └──> app.py  ──> 웹 대시보드
config.json + 명령 인자 ──> config            plotter(PNG)  exporter(저장·로그)
```

| 파일 | 역할 | 주요 함수 |
|---|---|---|
| [config.py](config.py) | 설정 파일과 명령 인자를 합쳐 `Settings` 생성 | `load_settings` |
| [loader.py](loader.py) | `facility_*` CSV 읽기, 시각순 병합, 불량코드 결합 | `read_facility_logs`, `merge_logs`, `attach_defect_info` |
| [aggregator.py](aggregator.py) | 모든 집계, 이상 기록, 조건 필터, 요약 | `facility_summary`, `defect_by_facility`, `find_anomalies`, `filter_logs`, `overall_summary` |
| [plotter.py](plotter.py) | matplotlib PNG 그래프 (한글 글꼴 자동 탐색) | `plot_defect_by_facility`, `plot_daily_defect_rate` |
| [exporter.py](exporter.py) | 폴더 생성, CSV·텍스트 저장, 실행 로그 | `save_csv`, `setup_run_logger` |
| [main.py](main.py) | 위 모듈을 순서대로 묶는 실행 파일 | `load_all_logs`, `run` |
| [app.py](app.py) | Dash 화면 | `build_view` |
| [tests/](tests/) | pytest 테스트 38개 | |

데이터의 흐름은 하나다. `main.load_all_logs()`가 시설 로그를 읽어 합친 DataFrame(이하 **전체 로그**)을 만들고, 모든 집계 함수는 이 DataFrame을 받는다. 전체 로그에는 원본 14개 열에 `defect_name`, `category`, `severity`가 붙어 있다.

## 3. 반드시 지켜야 하는 규칙

과제 명세에서 온 규칙이라 어기면 감점 대상이다.

1. **집계 코드는 `aggregator.py`와 기능별 분석 모듈(예: `spike.py`)에만 둔다.** ([ADR-001](docs/decisions/ADR-001-feature-modules.md)) `app.py`에 `groupby`, `pivot_table`, `value_counts`를 쓰면 테스트(`test_d7_app_has_no_aggregation_code`)가 실패한다. Dash가 필요한 집계는 `aggregator.py`에 함수를 추가하고 호출한다. 처리 프로그램과 대시보드의 숫자가 어긋나지 않게 하려는 규칙이다.
2. **대시보드는 로그를 시작할 때 한 번만 읽는다.** 콜백 안에서 CSV를 다시 읽지 않는다.
3. **파일 이름, 폴더, 기준값을 코드에 적지 않는다.** `config.py`의 `Settings`에 항목을 추가하고 `config.json`에 기본값을 둔다.
4. **파일 입출력에는 항상 인코딩을 지정한다.** 읽을 때는 `utf-8-sig`, CSV를 저장할 때는 `exporter.save_csv`를 쓴다. 이렇게 해야 엑셀에서 한글이 깨지지 않는다.
5. **문제 파일 하나가 전체를 멈추면 안 된다.** 읽을 수 없는 파일은 건너뛰고 `run_log.txt`에 이유를 남긴다.
6. **시설이 늘어도 코드를 고치지 않아야 한다.** 시설 이름이나 개수를 코드에 하드코딩하지 않는다.

## 4. 알아 두면 시간을 아끼는 설계 결정

| 항목 | 현재 동작 | 이유 |
|---|---|---|
| 불량의 정의 | `result == "NG"`. 판정 불가(D99)도 포함 | 로그에서 D99도 NG로 기록됨 |
| 이상 기록 | D99이거나 `process_ms` **초과**(`>`). 같은 값은 제외 | 명세의 "넘는" 해석 |
| `defect_types` 인자 | 검사 수(분모)는 그대로, 불량 수(분자)만 해당 종류로 제한 | 행을 거르면 불량률이 항상 100%가 됨. 집계 함수 대부분이 이 인자를 받는다 |
| `filter_logs` | 행 자체를 거름. 끝 날짜는 그날 24시까지 포함 | 필터 CSV 저장용(F9) |
| 정렬 | `mergesort`(안정 정렬) | 같은 시각 기록의 순서가 실행마다 바뀌지 않게 |
| `app.py`의 명령 인자 | `python app.py`로 직접 실행할 때만 읽음 | import 시 pytest 인자와 충돌 방지 |
| 그래프 구현이 둘 | PNG는 `plotter.py`(matplotlib), 화면은 `app.py`(Plotly) | 용도가 달라 분리. 그래프를 바꾸면 양쪽을 확인한다 |

## 5. 기능을 추가하는 방법

### 새 집계를 추가할 때
1. `aggregator.py`에 함수를 만든다. 전체 로그를 받아 DataFrame을 돌려주게 하고, 가능하면 `_count_table`을 재사용한다.
2. `main.py`의 `run()`에서 호출해 `exporter.save_csv`로 저장하고, 파일 이름은 상단의 `OUT_*` 상수로 둔다.
3. 화면에 필요하면 `app.py`의 `build_view()`에서 호출한다.
4. `tests/test_aggregator.py`에 테스트를 추가한다. 기대값은 구현이 아니라 손으로 계산한 값으로 정한다.
5. [README.md](README.md)의 출력 파일 표에 추가한다.

### 새 시설 로그를 추가할 때
코드를 고치지 않는다. `input/`에 `facility_`로 시작하는 CSV를 넣으면 된다. 열 구성은 `loader.REQUIRED_COLUMNS`와 같아야 하고, 다르면 건너뛰고 `run_log.txt`에 기록된다.

### 새 화면 요소를 추가할 때
`app.py`의 `app.layout`에 컴포넌트를 추가하고, `update()` 콜백의 `Output`과 `build_view()`의 반환값에 항목을 추가한다. `build_view()`는 브라우저 없이 테스트할 수 있으므로 계산은 거기에 두고 `tests/test_app.py`에 테스트를 넣는다.

## 6. 남은 작업과 시작점

| 작업 | 시작점 |
|---|---|
| **O1** 불량 박스 중심점·면적·위치 분포 | 로그의 `box_x1`, `box_y1`, `box_x2`, `box_y2`가 이미 숫자형으로 읽힌다. 사진 크기는 1280×1024. OK 기록과 D99는 좌표가 비어 있으니 NG이면서 D99가 아닌 행만 쓴다. 계산 함수는 `aggregator.py`에 추가하고 Dash에 표시한다 |
| **O2** 불량 급증 자동 탐지 (`feat/spike-detection`에서 구현, `spike.py`) | "크게 늘었다"의 기준을 먼저 정하고 문서에 설명해야 한다. 날짜·시설·카메라별 불량률이 평소 대비 얼마나 벗어났는지 보는 방식이 후보다. 데이터에서 이미 보이는 급증은 A-CAM1 11/20(D99 11건), C시설 11/19(치수 초과 21건), B시설 11/18(이물 15건)이다. 구현한 탐지가 이 세 건을 찾는지가 좋은 검증이 된다 |
| D99를 불량에서 뺀 불량률 | 현재는 D99를 항상 불량에 센다. `Settings`에 옵션을 추가하는 방식이 자연스럽다 |
| ~~한글 글꼴이 없는 환경~~ | 완료: `fonts/`에 나눔고딕 동봉, 시스템 글꼴이 없을 때 자동 사용 |

## 7. 작업 방식 (Git)

> 충돌 예방 규칙, 충돌 해결 절차, 작업 기록 방법은 [docs/collaboration.md](docs/collaboration.md)에 있다. PR 전에 `bash scripts/sync_check.sh`를 실행한다.

`main`에 직접 push하지 않는다. 기능마다 브랜치를 만들고 PR을 올려 squash merge한다.

```bash
git checkout main && git pull
git checkout -b feat/기능이름        # 예: feat/box-analysis
# ... 코드와 테스트 작성 ...
python -m pytest tests -q            # 통과 확인
git add 파일들
git commit -m "feat: 박스 면적 집계 추가 (O1)"
git push -u origin feat/기능이름
gh pr create --base main --title "feat: ..." --body-file pr.md
```

| 접두어 | 용도 |
|---|---|
| `feat:` | 기능 추가 |
| `fix:` | 버그 수정 |
| `docs:` | 문서 |
| `chore:` | 설정, 폴더 정리 등 |
| `test:` | 테스트만 변경 |

**PR 전에 확인할 것**
- `python -m pytest tests -q`가 통과하고 skipped가 0이다.
- 집계를 바꿨다면 `python main.py` 결과(전체 5,198건, 불량 238건, 4.58%)가 의도한 것과 다른지 비교한다. 의도한 변경이 아니면 원인을 찾는다.
- 화면을 바꿨다면 `python app.py`를 실제로 띄워 브라우저에서 선택을 바꿔 본다. 테스트만으로는 레이아웃과 콜백 연결 오류를 잡지 못한다.
- 제공 데이터(`input/`)와 결과(`output/`)는 `.gitignore`에 들어 있어 올라가지 않는다. `git status`로 CSV가 포함되지 않았는지 확인한다.
- 코드에는 한글 주석을 단다. 왜 그렇게 했는지가 드러나게 쓴다.
- AI 도구로 작성한 부분은 [AI_USAGE.md](AI_USAGE.md)에 요청, 결과, 직접 고친 부분을 추가한다. 이 과제는 제출한 코드를 직접 설명할 수 있어야 한다.

## 8. 자주 만나는 문제

| 증상 | 원인과 해결 |
|---|---|
| Windows에서 `gh`나 `git`을 찾을 수 없음 | 설치 직후 열려 있던 터미널은 PATH가 갱신되지 않는다. 터미널(VS Code)을 완전히 껐다 켠다 |
| PowerShell에서 `gh pr create --body "..."`가 실패함 | 본문에 큰따옴표가 있으면 인자가 쪼개진다. 본문을 파일로 저장하고 `--body-file`로 넘긴다 |
| `git add` 때 `LF will be replaced by CRLF` 경고 | Windows의 줄바꿈 경고이며 동작에는 문제 없다 |
| 그래프의 한글이 네모로 보임 | 시스템 글꼴과 `fonts/` 동봉 글꼴이 모두 없는 경우다. `fonts/NanumGothic-Regular.ttf`가 있는지, `plotter.setup_korean_font()`가 `None`을 돌려주는지 확인한다 |
| CSV를 엑셀에서 열면 한글이 깨짐 | 직접 `to_csv`를 쓰지 말고 `exporter.save_csv`(BOM 포함 UTF-8)로 저장한다 |
| 테스트가 skipped로 나옴 | `input/`에 제공 데이터가 없다 |

## 9. 환경 정보

개발과 검증은 Python 3.15.2, pandas 3.1.1, matplotlib 3.11.2, dash 4.5.1에서 했다. 다른 버전에서는 확인하지 않았으므로 버전 차이로 문제가 생기면 이슈로 남긴다.
