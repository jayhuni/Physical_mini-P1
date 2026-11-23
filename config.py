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
    return parser


def load_settings(argv: list[str] | None = None) -> Settings:
    """명령 인자와 설정 파일을 합쳐 Settings를 만든다."""
    args = build_parser().parse_args(argv)
    merged = load_config_file(args.config)

    # 명령 인자가 주어졌을 때만 설정 파일 값을 덮어쓴다
    for name in ("input_dir", "output_dir", "process_ms_threshold"):
        value = getattr(args, name)
        if value is not None:
            merged[name] = value

    # Settings에 정의된 항목만 사용한다 (설정 파일의 알 수 없는 키는 무시)
    allowed = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in merged.items() if k in allowed})
