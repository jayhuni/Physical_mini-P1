"""설정 관리 모듈 (S2).

입력 폴더, 출력 폴더, 처리 시간 기준값을 코드에 직접 적지 않고
설정 파일(config.json)과 명령 인자로 받는다.

우선순위: 명령 인자 > 설정 파일 > 기본값
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, fields
from pathlib import Path

# 설정 파일이 없을 때 쓰는 기본값
DEFAULT_CONFIG_PATH = "config.json"


@dataclass
class Settings:
    """프로그램 전체에서 공유하는 설정값 묶음."""

    input_dir: str = "."                        # 시설 로그 CSV가 있는 폴더
    output_dir: str = "output"                  # 처리 결과를 저장할 폴더
    process_ms_threshold: float = 1000.0        # 이 값(ms)을 넘으면 이상 기록
    facility_file_prefix: str = "facility_"     # 시설 로그 파일 이름 접두어 (F1)
    defect_codes_file: str = "defect_codes.csv"  # 불량코드표 파일 이름
    csv_encoding: str = "utf-8-sig"             # 저장 CSV 인코딩 (엑셀 한글 호환, S5)

    # F9 조건 필터. 일부만 지정해도 되고, 모두 비워 두면 필터 결과를 만들지 않는다
    facilities: list[str] | None = None         # 예: ["A시설", "B시설"]
    start_date: str | None = None               # 예: "2026-11-16"
    end_date: str | None = None                 # 예: "2026-11-18"
    defect_types: list[str] | None = None       # 불량 코드(D01) 또는 이름(스크래치)

    # O2 불량 급증 탐지 기준 (spike.py, docs/decisions/ADR-002-spike-criterion.md)
    spike_min_count: int = 5                    # 그날 불량이 이 건수 이상이어야 급증 후보
    spike_ratio: float = 3.0                    # 평소 기대 건수의 이 배수 이상
    spike_max_p: float = 0.0001                 # 평소 수준에서 우연히 나올 확률이 이 값 이하

    # 판정 불가(D99)를 불량률 집계의 불량으로 셀지. 이상 기록·급증 탐지에는 영향 없음
    count_d99_as_defect: bool = True

    # O1 불량 박스 분석 (box.py). 사진 크기는 명세의 값, 격자는 위치 분포를 볼 칸 수
    image_width: int = 1280
    image_height: int = 1024
    box_grid_cols: int = 4
    box_grid_rows: int = 4


def load_config_file(path: str | Path) -> dict:
    """JSON 설정 파일을 읽어 딕셔너리로 돌려준다. 파일이 없으면 빈 딕셔너리."""
    path = Path(path)
    if not path.exists():
        return {}
    # 인코딩을 명시해 읽는다 (S5)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_parser() -> argparse.ArgumentParser:
    """명령 인자 파서를 만든다. 지정하지 않은 인자는 None으로 두어 설정 파일 값을 살린다."""
    parser = argparse.ArgumentParser(description="비전검사 로그 통합 처리 프로그램")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="설정 파일 경로")
    parser.add_argument("--input-dir", help="시설 로그 CSV가 있는 입력 폴더")
    parser.add_argument("--output-dir", help="처리 결과를 저장할 출력 폴더")
    parser.add_argument("--threshold", type=float, dest="process_ms_threshold",
                        help="이상 기록 판단용 처리 시간 기준값(ms)")
    # F9 조건 필터 (모두 선택 사항)
    parser.add_argument("--facility", nargs="+", dest="facilities", help="시설 이름 (여러 개 가능)")
    parser.add_argument("--start-date", help="시작 날짜 (예: 2026-11-16)")
    parser.add_argument("--end-date", help="끝 날짜 (예: 2026-11-18, 그날 포함)")
    parser.add_argument("--defect", nargs="+", dest="defect_types", help="불량 코드 또는 이름 (여러 개 가능)")
    # 주지 않으면 None으로 남아 설정 파일 값을 쓴다
    parser.add_argument("--exclude-d99", action="store_const", const=False, dest="count_d99_as_defect",
                        help="판정 불가(D99)를 불량률 집계에서 불량으로 세지 않음")
    return parser


def load_settings(argv: list[str] | None = None) -> Settings:
    """명령 인자와 설정 파일을 합쳐 Settings를 만든다."""
    args = build_parser().parse_args(argv)
    merged = load_config_file(args.config)

    # 명령 인자가 주어졌을 때만 설정 파일 값을 덮어쓴다
    for name in ("input_dir", "output_dir", "process_ms_threshold",
                 "facilities", "start_date", "end_date", "defect_types", "count_d99_as_defect"):
        value = getattr(args, name)
        if value is not None:
            merged[name] = value

    # Settings에 정의된 항목만 사용한다 (설정 파일의 알 수 없는 키는 무시)
    allowed = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in merged.items() if k in allowed})
