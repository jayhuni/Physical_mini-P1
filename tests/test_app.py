"""Dash 화면 로직 테스트 (D3~D6). 브라우저 없이 build_view 와 aggregator 확장을 검사한다."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aggregator as agg
from tests.test_aggregator import make_df


def test_defect_type_keeps_denominator_so_rate_is_meaningful():
    # 시설 A: 4건 중 불량 2(D01, D99). 불량 종류를 D01로 고르면 분자만 1로 줄어야 한다
    s = agg.facility_summary(make_df(), defect_types=["D01"]).set_index("facility")
    assert s.loc["A시설", "검사수"] == 4 and s.loc["A시설", "불량수"] == 1
    assert s.loc["A시설", "불량률(%)"] == 25.0  # 100%가 아니다


def test_overall_summary_with_defect_types():
    s = agg.overall_summary(make_df(), defect_types=["스크래치"])
    assert (s["total"], s["defects"]) == (6, 1) and s["top_defect"] == "스크래치"


def test_default_behavior_unchanged_without_defect_types():
    assert agg.overall_summary(make_df())["defects"] == 3


@pytest.fixture(scope="module")
def view_module(tmp_path_factory):
    """app 모듈은 import 시 제공 데이터를 읽으므로, 데이터가 없으면 건너뛴다."""
    if not Path("facility_A_log.csv").exists():
        pytest.skip("제공 데이터가 없어 화면 통합 테스트를 건너뜀")
    import app
    return app


def test_d6_selection_changes_every_output(view_module):
    app = view_module
    full = app.build_view(app.LOGS, None, None, None, None, 1000)
    only_b = app.build_view(app.LOGS, ["B시설"], None, None, None, 1000)
    assert full["summary"]["total"] == 5198 and only_b["summary"]["total"] == 1352
    assert only_b["summary"]["defects"] == 56
    assert list(only_b["table"]["facility"]) == ["B시설"]
    assert set(only_b["anomalies"]["facility"]) <= {"B시설"}
    assert len(full["anomalies"]) == 11 and len(only_b["anomalies"]) == 0  # B시설은 이상 기록 없음


def test_d6_date_range_and_defect_type(view_module):
    app = view_module
    one_day = app.build_view(app.LOGS, None, "2026-11-16", "2026-11-16", None, 1000)
    assert 0 < one_day["summary"]["total"] < 5198
    scratch = app.build_view(app.LOGS, None, None, None, ["스크래치"], 1000)
    assert scratch["summary"]["defects"] == 77 and scratch["summary"]["total"] == 5198
    # 요약 카드의 이상 기록 수는 표에 보이는 행 수와 같아야 한다 (스크래치 기록 중 이상 기록은 없음)
    assert scratch["summary"]["anomalies"] == len(scratch["anomalies"]) == 0


def test_d6_empty_selection_does_not_crash(view_module):
    app = view_module
    v = app.build_view(app.LOGS, ["없는시설"], None, None, None, 1000)
    assert v["summary"]["total"] == 0 and v["summary"]["defect_rate"] == 0.0
    assert v["table"].empty and v["anomalies"].empty


def test_d7_app_has_no_aggregation_code(view_module):
    src = Path(view_module.__file__).read_text(encoding="utf-8")
    for banned in (".groupby(", ".pivot_table(", ".value_counts("):
        assert banned not in src, f"app.py 안에 집계 코드({banned})가 있습니다"
