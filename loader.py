"""읽기·합치기 모듈 (F1, F2, F3, S4).

시설별 로그 CSV를 읽어 하나로 합치고, 불량코드표를 결합한다.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

# 시설 로그가 반드시 가져야 하는 열. 하나라도 없으면 그 파일은 건너뛴다 (S4)
REQUIRED_COLUMNS = [
    "timestamp", "facility", "camera_id", "product_code", "serial_no",
    "result", "defect_code", "confidence",
    "box_x1", "box_y1", "box_x2", "box_y2", "process_ms", "image_file",
]
DEFECT_CODE_COLUMNS = ["defect_code", "defect_name", "category", "severity"]


def find_facility_logs(input_dir: str | Path, prefix: str = "facility_") -> list[Path]:
    """입력 폴더에서 이름이 prefix로 시작하는 CSV를 모두 찾는다 (F1).

    파일 이름이나 개수를 코드에 적지 않으므로 시설이 늘어도 코드 수정이 필요 없다.
    """
    return sorted(Path(input_dir).glob(f"{prefix}*.csv"))


def read_facility_log(path: Path) -> pd.DataFrame:
    """시설 로그 CSV 한 개를 읽어 형식을 정리한다.

    문제가 있으면 예외를 던진다. 호출한 쪽(read_facility_logs)이 잡아서 건너뛴다.
    """
    # BOM이 있는 UTF-8도 읽을 수 있도록 utf-8-sig로 명시 (S5)
    # 일련번호·코드는 문자열로 읽어 앞자리 0 같은 값이 변형되지 않게 한다
    df = pd.read_csv(path, encoding="utf-8-sig",
                     dtype={"serial_no": str, "defect_code": str, "product_code": str})

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"필요한 열이 없음: {', '.join(missing)}")

    df = df[REQUIRED_COLUMNS].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    for col in ("confidence", "box_x1", "box_y1", "box_x2", "box_y2", "process_ms"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def read_facility_logs(input_dir: str | Path, prefix: str,
                       logger: logging.Logger) -> list[pd.DataFrame]:
    """시설 로그를 모두 읽는다. 읽을 수 없는 파일은 건너뛰고 이유를 로그에 남긴다 (S4)."""
    frames: list[pd.DataFrame] = []
    for path in find_facility_logs(input_dir, prefix):
        try:
            df = read_facility_log(path)
        except Exception as exc:  # 파일 하나의 문제로 전체가 멈추지 않게 한다
            logger.warning("파일 건너뜀: %s (이유: %s: %s)", path.name, type(exc).__name__, exc)
            continue

        # 검사 시각을 해석할 수 없는 행은 시각 정렬이 불가능하므로 제외하고 알린다
        bad = int(df["timestamp"].isna().sum())
        if bad:
            logger.warning("%s: 검사 시각을 읽을 수 없는 %d행 제외", path.name, bad)
            df = df.dropna(subset=["timestamp"])
        logger.info("읽음: %s (%d행)", path.name, len(df))
        frames.append(df)
    return frames


def merge_logs(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """시설별 로그를 하나로 합치고 검사 시각 순으로 정렬한다 (F2)."""
    if not frames:
        raise ValueError("읽을 수 있는 시설 로그가 없습니다")
    merged = pd.concat(frames, ignore_index=True)
    # 같은 시각 기록의 순서가 실행마다 달라지지 않도록 안정 정렬(mergesort)을 쓴다
    return merged.sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def load_defect_codes(path: str | Path) -> pd.DataFrame:
    """불량코드표를 읽는다."""
    codes = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    missing = [c for c in DEFECT_CODE_COLUMNS if c not in codes.columns]
    if missing:
        raise ValueError(f"불량코드표에 필요한 열이 없음: {', '.join(missing)}")
    return codes[DEFECT_CODE_COLUMNS]


def attach_defect_info(logs: pd.DataFrame, codes: pd.DataFrame) -> pd.DataFrame:
    """전체 로그에 불량 이름, 분류, 심각도 열을 붙인다 (F3).

    left 결합이라 OK(불량 코드 없음) 기록도 그대로 남고 새 열만 빈칸이 된다.
    """
    return logs.merge(codes, on="defect_code", how="left")
