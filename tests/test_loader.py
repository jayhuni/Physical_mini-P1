"""loader / exporter / config 테스트.

기대값은 구현이 아니라 과제 명세(F1~F3, S2~S5)에서 가져온다.
테스트용 CSV는 임시 폴더에 직접 만들어 쓴다. 제공 데이터에 의존하지 않는다.
"""
import logging
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import exporter
import loader

HEADER = ",".join(loader.REQUIRED_COLUMNS)


def make_log(path: Path, rows: list[str]) -> None:
    """BOM 포함 UTF-8로 테스트용 로그 CSV를 만든다 (제공 데이터와 같은 형식)."""
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8-sig")


def row(ts, fac, cam="X-CAM1", result="OK", code="", ms=100):
    return f"{ts},{fac},{cam},P-1,S{ts[-8:].replace(':','')},{result},{code},0.9,,,,,{ms},img.jpg"


@pytest.fixture
def logger():
    return logging.getLogger("test_loader")


def test_f1_finds_every_facility_file_without_hardcoded_names(tmp_path):
    # 시설 3개 + 관련 없는 파일 1개 -> 접두어가 맞는 3개만 찾아야 한다
    for name in ("facility_A_log.csv", "facility_B_log.csv", "facility_Z_new.csv", "other.csv"):
        make_log(tmp_path / name, [row("2026-11-16 08:00:00", "A")])
    found = [p.name for p in loader.find_facility_logs(tmp_path, "facility_")]
    assert found == ["facility_A_log.csv", "facility_B_log.csv", "facility_Z_new.csv"]


def test_f2_merge_sorts_by_timestamp(tmp_path, logger):
    make_log(tmp_path / "facility_A_log.csv", [row("2026-11-16 08:05:00", "A"), row("2026-11-16 08:01:00", "A")])
    make_log(tmp_path / "facility_B_log.csv", [row("2026-11-16 08:03:00", "B")])
    merged = loader.merge_logs(loader.read_facility_logs(tmp_path, "facility_", logger))
    assert len(merged) == 3
    assert merged["timestamp"].is_monotonic_increasing
    assert list(merged["facility"]) == ["A", "B", "A"]


def test_s4_skips_file_with_missing_columns_and_logs_reason(tmp_path):
    make_log(tmp_path / "facility_A_log.csv", [row("2026-11-16 08:00:00", "A")])
    (tmp_path / "facility_BAD_log.csv").write_text("timestamp,facility\n2026-11-16 08:00:00,B\n", encoding="utf-8")
    logger = exporter.setup_run_logger(tmp_path / "out")
    frames = loader.read_facility_logs(tmp_path, "facility_", logger)
    assert len(frames) == 1  # 멈추지 않고 정상 파일만 읽는다
    log_text = (tmp_path / "out" / exporter.RUN_LOG_NAME).read_text(encoding="utf-8")
    assert "facility_BAD_log.csv" in log_text and "필요한 열이 없음" in log_text


def test_s4_skips_unreadable_file(tmp_path):
    make_log(tmp_path / "facility_A_log.csv", [row("2026-11-16 08:00:00", "A")])
    (tmp_path / "facility_BIN_log.csv").write_bytes(b"\xff\xfe\x00\x81\x82\x83")  # UTF-8이 아닌 바이트
    logger = exporter.setup_run_logger(tmp_path / "out2")
    assert len(loader.read_facility_logs(tmp_path, "facility_", logger)) == 1
    assert "facility_BIN_log.csv" in (tmp_path / "out2" / exporter.RUN_LOG_NAME).read_text(encoding="utf-8")


def test_merge_with_no_readable_files_raises():
    with pytest.raises(ValueError):
        loader.merge_logs([])


def test_f3_attach_defect_info_keeps_ok_rows(tmp_path, logger):
    make_log(tmp_path / "facility_A_log.csv",
             [row("2026-11-16 08:00:00", "A"), row("2026-11-16 08:01:00", "A", result="NG", code="D01")])
    codes = pd.DataFrame({"defect_code": ["D01"], "defect_name": ["스크래치"],
                          "category": ["외관"], "severity": ["B"]})
    merged = loader.merge_logs(loader.read_facility_logs(tmp_path, "facility_", logger))
    out = loader.attach_defect_info(merged, codes)
    assert len(out) == 2  # OK 기록이 사라지면 안 된다
    ng = out[out["result"] == "NG"].iloc[0]
    assert (ng["defect_name"], ng["category"], ng["severity"]) == ("스크래치", "외관", "B")
    assert pd.isna(out[out["result"] == "OK"].iloc[0]["defect_name"])


def test_s3_s5_save_csv_creates_folder_and_writes_bom(tmp_path):
    target = tmp_path / "new" / "deep" / "x.csv"  # 없는 폴더
    exporter.save_csv(pd.DataFrame({"이름": ["스크래치"]}), target)
    assert target.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM -> 엑셀에서 한글 정상
    assert pd.read_csv(target, encoding="utf-8-sig")["이름"][0] == "스크래치"


def test_s2_cli_overrides_config_file(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text('{"input_dir": "from_file", "output_dir": "out_file", "process_ms_threshold": 500}',
                   encoding="utf-8")
    s = config.load_settings(["--config", str(cfg), "--output-dir", "out_cli"])
    assert (s.input_dir, s.output_dir, s.process_ms_threshold) == ("from_file", "out_cli", 500)


def test_s2_defaults_when_no_config_file(tmp_path):
    s = config.load_settings(["--config", str(tmp_path / "none.json")])
    assert s.process_ms_threshold == 1000  # 명세의 기본값
