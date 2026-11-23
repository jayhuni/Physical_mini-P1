"""plotter / main 파이프라인 테스트 (F10, F11, S3, S4, S6)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import main
import plotter
from tests.test_loader import make_log, row  # 테스트용 로그 생성 도구 재사용


@pytest.fixture
def input_dir(tmp_path):
    """시설 2개 + 불량코드표가 든 입력 폴더."""
    d = tmp_path / "in"
    d.mkdir()
    make_log(d / "facility_A_log.csv", [
        row("2026-11-16 08:00:00", "A시설", "A-CAM1"),
        row("2026-11-17 08:01:00", "A시설", "A-CAM1", result="NG", code="D01"),
        row("2026-11-17 08:02:00", "A시설", "A-CAM2", result="NG", code="D99", ms=1500),
    ])
    make_log(d / "facility_B_log.csv", [
        row("2026-11-16 09:00:00", "B시설", "B-CAM1"),
        row("2026-11-17 09:01:00", "B시설", "B-CAM1", result="NG", code="D03"),
    ])
    (d / "defect_codes.csv").write_text(
        "defect_code,defect_name,category,severity\nD01,스크래치,외관,B\nD03,이물,외관,C\nD99,판정 불가,시스템,-\n",
        encoding="utf-8-sig")
    return d


def run_with(input_dir, output_dir, *extra):
    cfg = input_dir.parent / "none.json"  # 없는 설정 파일 -> 기본값 사용
    return main.run(config.load_settings(["--config", str(cfg), "--input-dir", str(input_dir),
                                          "--output-dir", str(output_dir), *extra]))


def test_s6_one_command_creates_all_outputs(input_dir, tmp_path):
    out = tmp_path / "out" / "nested"  # 없는 폴더도 자동 생성 (S3)
    assert run_with(input_dir, out) == 0
    for name in (main.OUT_ALL_LOGS, main.OUT_FACILITY, main.OUT_DEFECT_BY_FACILITY,
                 main.OUT_DEFECT_BY_CATEGORY, main.OUT_DAILY, main.OUT_CAMERA,
                 main.OUT_ANOMALIES, main.OUT_SUMMARY, main.OUT_CHART_DEFECT,
                 main.OUT_CHART_DAILY, "run_log.txt"):
        assert (out / name).exists(), f"{name} 누락"
    assert not (out / main.OUT_FILTERED).exists()  # 조건 없으면 필터 결과 없음


def test_f2_f3_all_log_is_sorted_and_has_defect_columns(input_dir, tmp_path):
    run_with(input_dir, tmp_path / "o")
    df = pd.read_csv(tmp_path / "o" / main.OUT_ALL_LOGS, encoding="utf-8-sig", parse_dates=["timestamp"])
    assert len(df) == 5 and df["timestamp"].is_monotonic_increasing
    assert {"defect_name", "category", "severity"} <= set(df.columns)


def test_f9_filter_cli_saves_only_matching(input_dir, tmp_path):
    run_with(input_dir, tmp_path / "o", "--facility", "A시설", "--start-date", "2026-11-17")
    picked = pd.read_csv(tmp_path / "o" / main.OUT_FILTERED, encoding="utf-8-sig")
    assert len(picked) == 2 and set(picked["facility"]) == {"A시설"}


def test_f8_threshold_from_cli(input_dir, tmp_path):
    run_with(input_dir, tmp_path / "o", "--threshold", "50")  # 기준을 낮추면 이상 기록이 늘어난다
    assert len(pd.read_csv(tmp_path / "o" / main.OUT_ANOMALIES, encoding="utf-8-sig")) == 5


def test_f11_summary_file_and_screen(input_dir, tmp_path, capsys):
    run_with(input_dir, tmp_path / "o")
    text = (tmp_path / "o" / main.OUT_SUMMARY).read_text(encoding="utf-8")
    assert "전체 검사 수      : 5건" in text and "전체 불량 수      : 3건" in text
    assert "전체 검사 수" in capsys.readouterr().out  # 화면에도 출력


def test_s4_no_readable_logs_returns_error_not_crash(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert run_with(empty, tmp_path / "o") == 1
    assert "처리 중단" in (tmp_path / "o" / "run_log.txt").read_text(encoding="utf-8")


def test_f10_korean_font_found_and_png_is_valid(tmp_path):
    font = plotter.setup_korean_font()
    assert font is not None, "한글 글꼴이 설치되어 있지 않아 그래프의 한글이 깨집니다"
    table = pd.DataFrame({"facility": ["A시설", "B시설"], "스크래치": [3, 1], "이물": [0, 2]})
    png = plotter.plot_defect_by_facility(table, tmp_path / "a.png")
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_f10_bundled_font_used_when_no_system_korean_font(tmp_path):
    # 시스템 한글 글꼴이 하나도 없는 PC를 흉내 낸다: 후보 목록을 없는 이름으로 바꾼다
    name = plotter.setup_korean_font(candidates=["없는글꼴"])
    assert name == "NanumGothic"  # fonts/ 에 동봉한 글꼴
    import matplotlib.pyplot as plt
    assert plt.rcParams["font.family"] == ["NanumGothic"]
    plotter.setup_korean_font()  # 다른 테스트를 위해 기본 동작으로 되돌린다
