# 비전검사 로그 통합 처리 프로그램

세 시설(A, B, C)의 비전검사 로그 CSV를 하나로 합치고, 불량을 종류별로 집계해 CSV·그래프·요약으로 저장하며, 웹 대시보드(Dash)로 조건을 바꿔 가며 볼 수 있는 프로그램이다. 과제 명세는 [비전검사_로그_통합_처리_프로그램_개발.md](비전검사_로그_통합_처리_프로그램_개발.md)에 있다.

## 필요한 패키지와 설치

Python 3.15.2, pandas 3.1.1, matplotlib 3.11.2, dash 4.5.1 에서 개발하고 검증했다. 다른 버전은 확인하지 않았다.

```bash
pip install -r requirements.txt
```

그래프의 한글은 설치된 한글 글꼴(Malgun Gothic, AppleGothic, NanumGothic 등)을 자동으로 찾아 쓴다. 한글 글꼴이 없는 PC에서는 그래프의 한글이 네모로 보일 수 있다.

## 데이터 준비

저장소에는 제공 데이터와 처리 결과를 올리지 않았다. 아래 4개 파일을 입력 폴더(기본: 프로젝트 폴더)에 직접 넣는다.

```
facility_A_log.csv  facility_B_log.csv  facility_C_log.csv  defect_codes.csv
```

`facility_`로 시작하는 CSV는 파일 이름이나 개수에 상관없이 모두 읽으므로 시설 로그가 늘어도 코드를 고칠 필요가 없다.

## 실행 방법

### 1) 전체 처리 (명령 한 줄)

```bash
python main.py
```

결과는 `output/` 폴더에 저장되고 요약은 화면에도 출력된다.

설정을 바꿔 실행하는 예:

```bash
# 입력/출력 폴더와 이상 기록 기준값(ms) 지정
python main.py --input-dir data --output-dir result --threshold 800

# 조건 필터 (F9): A시설, 11/17 이후, 스크래치와 판정 불가만
python main.py --facility A시설 --start-date 2026-11-17 --defect 스크래치 D99
```

### 2) Dash 화면

```bash
python app.py
```

브라우저에서 http://127.0.0.1:8050 을 연다. 위쪽에서 시설(여러 개), 날짜 범위, 불량 종류를 고르면 요약 숫자, 그래프 2개, 표 2개가 모두 다시 계산된다. 로그는 앱을 시작할 때 한 번만 읽는다.

### 3) 테스트

```bash
python -m pytest tests -q
```

## 설정 항목

[config.json](config.json)에 적고, 같은 항목을 명령 인자로 주면 명령 인자가 우선한다.

| 항목 | 명령 인자 | 기본값 | 설명 |
|---|---|---|---|
| `input_dir` | `--input-dir` | `.` | 시설 로그와 불량코드표가 있는 폴더 |
| `output_dir` | `--output-dir` | `output` | 결과 저장 폴더. 없으면 자동 생성 |
| `process_ms_threshold` | `--threshold` | `1000` | 이 값(ms)을 **넘는** 기록을 이상 기록으로 분류 |
| `facility_file_prefix` | - | `facility_` | 시설 로그 파일 이름 접두어 |
| `defect_codes_file` | - | `defect_codes.csv` | 불량코드표 파일 이름 |
| `csv_encoding` | - | `utf-8-sig` | 저장 CSV 인코딩. BOM 포함이라 엑셀에서 한글이 깨지지 않는다 |
| - | `--facility` | 없음 | F9 필터: 시설 이름 (여러 개 가능) |
| - | `--start-date` `--end-date` | 없음 | F9 필터: 날짜 범위 (양 끝 날짜 포함) |
| - | `--defect` | 없음 | F9 필터: 불량 코드 또는 이름 (여러 개 가능) |

## 출력 파일

| 파일 | 내용 | 요구사항 |
|---|---|---|
| `all_facility_log.csv` | 전체 시설 로그. 검사 시각순, 불량 이름·분류·심각도 열 포함 | F2, F3 |
| `facility_summary.csv` | 시설별 검사 수, 불량 수, 불량률(%) | F4 |
| `defect_by_facility.csv` | 시설 × 불량 종류 건수 | F5 |
| `defect_by_category.csv` | 불량 분류별 건수 | F5 |
| `daily_facility_summary.csv` | 날짜별·시설별 검사 수와 불량률 | F6 |
| `camera_summary.csv` | 카메라별 검사 수와 불량률 | F7 |
| `anomalies.csv` | 이상 기록 목록 (판정 불가 또는 처리 시간 초과, `reason` 열에 사유) | F8 |
| `filtered_logs.csv` | 조건 필터 결과. 필터 인자를 줬을 때만 생성 | F9 |
| `chart_defect_by_facility.png` | 시설별 불량 종류 건수 막대그래프 | F10 |
| `chart_daily_defect_rate.png` | 날짜별 시설 불량률 추이 그래프 | F10 |
| `summary.txt` | 전체 요약 | F11 |
| `run_log.txt` | 실행 로그. 건너뛴 파일과 이유가 기록된다 | S4 |

## 집계 기준

- **불량**은 `result`가 `NG`인 기록이다. 판정 불가(D99)도 `NG`로 기록되어 있어 불량 수에 포함한다. D99는 이상 기록에서도 별도로 분류된다.
- **이상 기록**은 D99이거나 `process_ms`가 기준값을 **초과**한 기록이다. 기준값과 같은 값은 포함하지 않는다.
- Dash에서 불량 종류를 고르면 검사 수(분모)는 시설·날짜 조건으로만 정해지고, 불량 수(분자)만 선택한 종류로 줄어든다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `main.py` | 전체 처리 실행 파일 (S6) |
| `app.py` | Dash 화면 (D1~D7) |
| `config.py` | 설정 파일과 명령 인자 처리 (S2) |
| `loader.py` | 시설 로그 읽기, 병합, 불량코드 결합 (F1~F3, S4) |
| `aggregator.py` | 집계, 이상 기록, 조건 필터, 요약 (F4~F9, F11) |
| `plotter.py` | PNG 그래프 (F10) |
| `exporter.py` | 폴더 생성, CSV·텍스트 저장, 실행 로그 (S3, S5) |
| `tests/` | pytest 테스트 |
| `.claude/skills/` | 개발에 사용한 외부 스킬. 출처는 [ATTRIBUTION.md](ATTRIBUTION.md) |
