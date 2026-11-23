"""aggregator 테스트. 손으로 계산 가능한 작은 데이터로 기대값을 직접 정한다."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aggregator as agg


def make_df() -> pd.DataFrame:
    """A: 4건 중 불량 2(D01, D99) / B: 2건 중 불량 1(D03) / 날짜 2일."""
    rows = [
        # timestamp, facility, camera, result, code, name, category, ms
        ("2026-11-16 08:00:00", "A시설", "A-CAM1", "OK", None, None, None, 100),
        ("2026-11-16 09:00:00", "A시설", "A-CAM1", "NG", "D01", "스크래치", "외관", 120),
        ("2026-11-17 10:00:00", "A시설", "A-CAM2", "NG", "D99", "판정 불가", "시스템", 1500),
        ("2026-11-17 11:00:00", "A시설", "A-CAM2", "OK", None, None, None, 1001),
        ("2026-11-16 09:30:00", "B시설", "B-CAM1", "OK", None, None, None, 90),
        ("2026-11-17 12:00:00", "B시설", "B-CAM1", "NG", "D03", "이물", "외관", 1000),
    ]
    return pd.DataFrame(rows, columns=["timestamp", "facility", "camera_id", "result",
                                       "defect_code", "defect_name", "category", "process_ms"]
                        ).assign(timestamp=lambda d: pd.to_datetime(d["timestamp"]))


def test_f4_facility_summary():
    out = agg.facility_summary(make_df()).set_index("facility")
    assert out.loc["A시설", "검사수"] == 4 and out.loc["A시설", "불량수"] == 2
    assert out.loc["A시설", "불량률(%)"] == 50.0
    assert out.loc["B시설", "불량률(%)"] == 50.0


def test_f4_rate_rounds_to_two_decimals():
    df = pd.concat([make_df().iloc[[1]]] + [make_df().iloc[[0]]] * 2, ignore_index=True)  # 1/3
    assert agg.facility_summary(df).iloc[0]["불량률(%)"] == 33.33


def test_f5_defect_by_facility_has_zero_fill():
    out = agg.defect_by_facility(make_df()).set_index("facility")
    assert out.loc["A시설", "스크래치"] == 1
    assert out.loc["B시설", "스크래치"] == 0  # 없던 조합은 0
    assert out.loc["B시설", "이물"] == 1


def test_f5_defect_by_category():
    out = agg.defect_by_category(make_df()).set_index("category")["건수"]
    assert out["외관"] == 2 and out["시스템"] == 1


def test_f6_daily_facility_summary():
    out = agg.daily_facility_summary(make_df())
    a_17 = out[(out["facility"] == "A시설") & (out["date"] == pd.Timestamp("2026-11-17").date())].iloc[0]
    assert a_17["검사수"] == 2 and a_17["불량수"] == 1 and a_17["불량률(%)"] == 50.0
    assert len(out) == 4  # (16일,17일) x (A,B)


def test_f7_camera_summary():
    out = agg.camera_summary(make_df()).set_index("camera_id")
    assert out.loc["A-CAM1", "검사수"] == 2 and out.loc["A-CAM1", "불량률(%)"] == 50.0
    assert out.loc["B-CAM1", "검사수"] == 2


def test_f8_anomalies_d99_or_over_threshold_strictly():
    out = agg.find_anomalies(make_df(), threshold_ms=1000)
    # D99(1500ms)와 1001ms는 포함, 정확히 1000ms는 '넘지 않으므로' 제외
    assert sorted(out["process_ms"]) == [1001, 1500]
    d99 = out[out["defect_code"] == "D99"].iloc[0]
    assert "판정 불가" in d99["reason"] and "처리 시간 초과" in d99["reason"]


def test_f8_threshold_is_configurable():
    assert len(agg.find_anomalies(make_df(), threshold_ms=100)) >= 4


def test_f8_empty_result_keeps_columns():
    out = agg.find_anomalies(make_df(), threshold_ms=99999).query("defect_code != 'D99'")
    assert "reason" in agg.find_anomalies(make_df().iloc[[0]], 1000).columns and len(out) == 0


def test_f9_partial_conditions_work():
    df = make_df()
    assert len(agg.filter_logs(df)) == 6  # 조건 없음 -> 전체
    assert len(agg.filter_logs(df, facilities=["B시설"])) == 2  # 시설만
    assert len(agg.filter_logs(df, defect_types=["D01"])) == 1  # 코드로
    assert len(agg.filter_logs(df, defect_types=["이물"])) == 1  # 이름으로
    assert len(agg.filter_logs(df, start_date="2026-11-17")) == 3  # 시작일만


def test_f9_end_date_includes_whole_day():
    out = agg.filter_logs(make_df(), start_date="2026-11-16", end_date="2026-11-16")
    assert len(out) == 3 and (out["timestamp"].dt.day == 16).all()


def test_f9_combined_conditions():
    out = agg.filter_logs(make_df(), facilities=["A시설"], start_date="2026-11-17", defect_types=["D99"])
    assert len(out) == 1


def test_f11_overall_summary():
    s = agg.overall_summary(make_df(), threshold_ms=1000)
    assert (s["total"], s["defects"], s["defect_rate"]) == (6, 3, 50.0)
    assert s["worst_facility"] in ("A시설", "B시설")
    assert s["anomalies"] == 2
    assert s["top_defect_count"] == 1


def test_f11_summary_handles_empty_filter_result():
    empty = make_df().iloc[0:0]
    s = agg.overall_summary(empty)
    assert s["total"] == 0 and s["defect_rate"] == 0.0 and s["worst_facility"] is None
    assert "해당 없음" in agg.format_summary_text(s)  # 빈 선택에서도 화면이 깨지지 않아야 한다 (D6)


def test_f11_text_contains_all_required_items():
    text = agg.format_summary_text(agg.overall_summary(make_df()))
    for label in ("전체 검사 수", "전체 불량 수", "전체 불량률", "불량률 최고 시설", "최다 불량 종류", "이상 기록 수"):
        assert label in text
