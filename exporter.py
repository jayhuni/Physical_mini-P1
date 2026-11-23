"""저장 모듈: 출력 폴더 준비, CSV/텍스트 저장, 실행 로그 (S3, S4, S5)."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

RUN_LOG_NAME = "run_log.txt"


def ensure_output_dir(output_dir: str | Path) -> Path:
    """출력 폴더가 없으면 상위 폴더까지 만들어 돌려준다 (S3)."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_csv(df: pd.DataFrame, path: str | Path, encoding: str = "utf-8-sig") -> Path:
    """DataFrame을 CSV로 저장한다.

    utf-8-sig(BOM 포함)로 저장해야 엑셀에서 열어도 한글이 깨지지 않는다 (S5).
    """
    path = Path(path)
    ensure_output_dir(path.parent)
    df.to_csv(path, index=False, encoding=encoding)
    return path


def save_text(text: str, path: str | Path, encoding: str = "utf-8") -> Path:
    """텍스트를 파일로 저장한다."""
    path = Path(path)
    ensure_output_dir(path.parent)
    with open(path, "w", encoding=encoding) as f:
        f.write(text)
    return path


def setup_run_logger(output_dir: str | Path) -> logging.Logger:
    """실행 로그(텍스트 파일) 기록기를 만든다 (S4).

    건너뛴 파일과 그 이유가 output_dir/run_log.txt 에 남는다.
    """
    out = ensure_output_dir(output_dir)
    logger = logging.getLogger(f"vision_log.{out.resolve()}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:  # 같은 폴더로 여러 번 호출해도 핸들러가 중복되지 않게 한다
        handler = logging.FileHandler(out / RUN_LOG_NAME, mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        logger.addHandler(logging.StreamHandler())  # 화면에도 같이 출력
    return logger
