"""불량 급증 탐지(O2) 테스트. 기대값은 아래 주석처럼 손으로 계산했다."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import spike


def make_days(counts, per_day=100, facility="X시설", camera="X-CAM1", code="D01", name="스크래치"):
    """날짜별로 per_day건 검사하고 그중 counts[i]건이 불량인 로그를 만든다.

    per_day에 리스트를 주면 날짜마다 검사 수를 다르게 할 수 있다.
    """
    if not isinstance(per_day, list):
        per_day = [per_day] * len(counts)
    rows = []
    for i, (ng, n) in enumerate(zip(counts, per_day)):
        day = pd.Timestamp("2026-11-16") + pd.Timedelta(days=i)
        for k in range(n):
            is_ng = k < ng
            rows.append({"timestamp": day + pd.Timedelta(minutes=k), "facility": facility,
                         "camera_id": camera, "result": "NG" if is_ng else "OK",
                         "defect_code": code if is_ng else None,
                         "defect_name": name if is_ng else None})
    return pd.DataFrame(rows)


def test_spike_found_against_other_days_baseline():
    # 3일 x 100건, 불량 1, 1, 8건.
    # 셋째 날 평소 = 다른 날 (1+1)/200 = 1% -> 기대 1.0건. 8건 = 8배, 5건 이상,
    # 우연 확률 P(X>=8 | 포아송 1.0) = 약 1.0e-5 <= 0.0001 -> 급증
    out = spike.detect_spikes(make_days([1, 1, 8]))
    assert len(out) == 2  # 시설 단위 1건 + 카메라 단위 1건
    assert set(out["단위"]) == {"시설", "카메라"}
    row = out[out["단위"] == "카메라"].iloc[0]
    assert str(row["날짜"]) == "2026-11-18"
    assert row["불량수"] == 8 and row["기대건수"] == 1.0 and row["배수"] == 8.0
    assert row["평소불량률(%)"] == 1.0 and row["당일불량률(%)"] == 8.0
    assert row["p값"] == pytest.approx(1.02e-5, rel=0.01)
    assert row["camera_id"] == "X-CAM1"
    assert pd.isna(out[out["단위"] == "시설"].iloc[0]["camera_id"])


def test_rate_not_count_more_inspections_is_not_spike():
    # 셋째 날 검사가 400건이면 평소 1%로 기대 4.0건. 8건은 2배라 3배 기준 미달
    out = spike.detect_spikes(make_days([1, 1, 8], per_day=[100, 100, 400]))
    assert out.empty


def test_min_count_boundary_when_baseline_is_zero():
    # 평소 0건이면 배수는 정의할 수 없으므로 최소 건수(5)로만 판단한다
    assert spike.detect_spikes(make_days([0, 0, 4])).empty
    out = spike.detect_spikes(make_days([0, 0, 5]))
    assert len(out) == 2 and out["불량수"].tolist() == [5, 5]
    assert out["기대건수"].tolist() == [0.0, 0.0] and out["배수"].isna().all()


def test_single_day_has_no_baseline():
    # 비교할 다른 날이 없으면 '평소'가 없으므로 탐지하지 않는다
    assert spike.detect_spikes(make_days([30])).empty


def test_thresholds_are_parameters():
    df = make_days([1, 1, 8])
    assert spike.detect_spikes(df, min_count=9).empty
    assert spike.detect_spikes(df, ratio=9.0).empty
    assert spike.detect_spikes(df, max_p=1e-6).empty


def test_spike_on_one_camera_reported_with_camera_id():
    # 같은 시설의 CAM2는 매일 1건으로 평소대로, CAM1만 셋째 날 급증
    df = pd.concat([make_days([1, 1, 8], camera="X-CAM1"), make_days([1, 1, 1], camera="X-CAM2")],
                   ignore_index=True)
    cams = spike.detect_spikes(df).query("단위 == '카메라'")
    assert cams["camera_id"].tolist() == ["X-CAM1"]


def test_select_spikes_by_facility_date_defect():
    df = pd.concat([make_days([1, 1, 8], facility="X시설", camera="X-CAM1"),
                    make_days([0, 6, 0], facility="Y시설", camera="Y-CAM1", code="D03", name="이물")],
                   ignore_index=True)
    out = spike.detect_spikes(df)
    assert len(out) == 4
    assert set(spike.select_spikes(out, facilities=["Y시설"])["facility"]) == {"Y시설"}
    assert set(spike.select_spikes(out, start_date="2026-11-18")["facility"]) == {"X시설"}
    assert set(spike.select_spikes(out, end_date="2026-11-17")["facility"]) == {"Y시설"}
    assert set(spike.select_spikes(out, defect_types=["이물"])["defect_code"]) == {"D03"}
    assert set(spike.select_spikes(out, defect_types=["D01"])["defect_code"]) == {"D01"}
    assert len(spike.select_spikes(out)) == 4


def test_format_spike_text():
    text = spike.format_spike_text(spike.detect_spikes(make_days([1, 1, 8])))
    assert "불량 급증 탐지" in text and "2건" in text
    assert "2026-11-18" in text and "X-CAM1" in text and "스크래치" in text
    assert "없음" in spike.format_spike_text(spike.detect_spikes(make_days([1, 1, 1])))


def test_settings_have_spike_defaults(tmp_path):
    s = config.load_settings(["--config", str(tmp_path / "none.json")])
    assert (s.spike_min_count, s.spike_ratio, s.spike_max_p) == (5, 3.0, 0.0001)


# ---------------------------------------------------------------- 제공 데이터 검증
def test_known_spikes_in_provided_data():
    """TEAM_README에 적힌, 데이터에서 눈으로 확인된 급증 3건을 모두 찾는지 본다."""
    settings = config.load_settings([])
    if not (Path(settings.input_dir) / "facility_A_log.csv").exists():
        pytest.skip("제공 데이터가 없어 급증 탐지 통합 검증을 건너뜀")
    import logging
    import main
    logs = main.load_all_logs(settings, logging.getLogger("test"))
    out = spike.detect_spikes(logs, settings.spike_min_count, settings.spike_ratio, settings.spike_max_p)
    day = out["날짜"].astype(str)

    def found(date, facility, name_part, camera=None):
        m = (day == date) & (out["facility"] == facility) & out["defect_name"].str.contains(name_part)
        if camera:
            m &= out["camera_id"] == camera
        return m.any()

    assert found("2026-11-20", "A시설", "판정 불가", camera="A-CAM1")
    assert found("2026-11-19", "C시설", "치수")
    assert found("2026-11-18", "B시설", "이물")


def test_dashboard_spike_table_follows_selection():
    """Dash 화면의 급증 표가 시설 선택을 따라 바뀌는지 본다 (app은 import 시 데이터를 읽으므로 데이터가 필요)."""
    if not (Path(config.load_settings([]).input_dir) / "facility_A_log.csv").exists():
        pytest.skip("제공 데이터가 없어 화면 통합 테스트를 건너뜀")
    import app
    full = app.build_view(app.LOGS, None, None, None, None, 1000, app.SPIKES)
    only_b = app.build_view(app.LOGS, ["B시설"], None, None, None, 1000, app.SPIKES)
    assert len(full["spikes"]) == len(app.SPIKES) > 0
    assert set(only_b["spikes"]["facility"]) <= {"B시설"}
    empty = app.build_view(app.LOGS, ["없는시설"], None, None, None, 1000, app.SPIKES)
    assert empty["spikes"].empty
