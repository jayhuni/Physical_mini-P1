"""불량 박스 분석(O1) 테스트. 기대값은 주석처럼 손으로 계산했다. 사진 1280x1024, 격자 4x4(칸 320x256)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import box
import config

W, H = 1280, 1024


def make_df() -> pd.DataFrame:
    rows = [
        # result, code, name, x1, y1, x2, y2
        ("NG", "D01", "스크래치", 0, 0, 100, 50),          # 중심 (50, 25), 100x50=5000, 칸(0,0)
        ("NG", "D01", "스크래치", 100, 100, 300, 200),     # 중심 (200, 150), 200x100=20000, 칸(0,0)
        ("NG", "D03", "이물", 1200, 1000, 1280, 1024),     # 중심 (1240, 1012), 80x24=1920, 칸(열3, 행3)
        ("NG", "D99", "판정 불가", None, None, None, None),  # 판정 불가: 좌표 없음 -> 대상 아님
        ("OK", None, None, None, None, None, None),         # 정상: 대상 아님
        ("NG", "D02", "찍힘", 500, 0, 400, 10),            # x2 < x1 -> 잘못된 좌표
        ("NG", "D02", "찍힘", 0, 0, 1300, 10),             # 사진 밖(1280 초과) -> 잘못된 좌표
    ]
    df = pd.DataFrame(rows, columns=["result", "defect_code", "defect_name",
                                     "box_x1", "box_y1", "box_x2", "box_y2"])
    df.insert(0, "timestamp", pd.Timestamp("2026-11-16 08:00:00"))
    df.insert(1, "facility", "A시설")
    df.insert(2, "camera_id", "A-CAM1")
    return df


def test_compute_boxes_center_area_and_invalid():
    boxes, invalid = box.compute_boxes(make_df(), W, H)
    assert len(boxes) == 3 and len(invalid) == 2
    first = boxes.iloc[0]
    assert (first["중심x"], first["중심y"], first["너비"], first["높이"], first["면적"]) == (50, 25, 100, 50, 5000)
    assert set(invalid["defect_code"]) == {"D02"}
    assert "D99" not in set(boxes["defect_code"])


def test_box_by_defect_means():
    boxes, _ = box.compute_boxes(make_df(), W, H)
    out = box.box_by_defect(boxes, W, H).set_index("defect_name")
    s = out.loc["스크래치"]
    assert s["건수"] == 2 and s["평균면적"] == 12500.0      # (5000 + 20000) / 2
    assert s["평균너비"] == 150.0 and s["평균높이"] == 75.0  # (100+200)/2, (50+100)/2
    assert s["평균중심x"] == 125.0 and s["평균중심y"] == 87.5
    assert s["면적비율(%)"] == 0.95                          # 12500 / (1280*1024) * 100 = 0.9537
    assert out.loc["이물", "평균면적"] == 1920.0
    # 건수가 많은 순서
    assert list(out.index) == ["스크래치", "이물"]


def test_position_grid_counts_and_all_cells():
    boxes, _ = box.compute_boxes(make_df(), W, H)
    grid = box.position_grid(boxes, W, H, cols=4, rows=4)
    total = grid[grid["defect_name"] == "전체"]
    assert len(total) == 16 and total["건수"].sum() == 3     # 빈 칸도 0으로 포함
    cell = total.set_index(["행", "열"])["건수"]
    assert cell[(0, 0)] == 2 and cell[(3, 3)] == 1
    scratch = grid[grid["defect_name"] == "스크래치"].set_index(["행", "열"])["건수"]
    assert scratch[(0, 0)] == 2 and scratch.sum() == 2
    first = total.set_index(["행", "열"]).loc[(0, 1)]
    assert (first["x시작"], first["x끝"], first["y시작"], first["y끝"]) == (320, 640, 0, 256)


def test_grid_cell_boundaries():
    # 중심이 칸 경계(320)에 정확히 있으면 오른쪽 칸, 사진 끝(1280, 1024)이면 마지막 칸
    df = make_df().iloc[[0]].copy()
    df[["box_x1", "box_y1", "box_x2", "box_y2"]] = [300, 0, 340, 10]          # 중심 x=320
    df2 = make_df().iloc[[0]].copy()
    df2[["box_x1", "box_y1", "box_x2", "box_y2"]] = [1280, 1024, 1280, 1024]  # 폭 0 -> 잘못된 좌표
    boxes, invalid = box.compute_boxes(pd.concat([df, df2]), W, H)
    assert len(boxes) == 1 and len(invalid) == 1
    grid = box.position_grid(boxes, W, H, 4, 4)
    cell = grid[grid["defect_name"] == "전체"].set_index(["행", "열"])["건수"]
    assert cell[(0, 1)] == 1


def test_position_matrix_for_heatmap():
    boxes, _ = box.compute_boxes(make_df(), W, H)
    m = box.position_matrix(box.position_grid(boxes, W, H, 4, 4))
    assert m.shape == (4, 4) and m.iloc[0, 0] == 2 and m.iloc[3, 3] == 1
    assert box.position_matrix(box.position_grid(boxes, W, H, 4, 4), "이물").to_numpy().sum() == 1


def test_empty_input():
    boxes, invalid = box.compute_boxes(make_df().iloc[[3, 4]], W, H)  # D99, OK만
    assert boxes.empty and invalid.empty
    assert box.box_by_defect(boxes, W, H).empty
    grid = box.position_grid(boxes, W, H, 4, 4)
    assert len(grid) == 16 and grid["건수"].sum() == 0


def test_settings_have_box_defaults(tmp_path):
    s = config.load_settings(["--config", str(tmp_path / "none.json")])
    assert (s.image_width, s.image_height, s.box_grid_cols, s.box_grid_rows) == (1280, 1024, 4, 4)


def test_pipeline_saves_box_outputs(tmp_path):
    import main
    from tests.test_loader import make_log, row
    d = tmp_path / "in"
    d.mkdir()
    make_log(d / "facility_A_log.csv", [
        row("2026-11-16 08:00:00", "A시설", "A-CAM1"),
        row("2026-11-16 08:01:00", "A시설", "A-CAM1", result="NG", code="D01"),
    ])
    (d / "defect_codes.csv").write_text("defect_code,defect_name,category,severity\nD01,스크래치,외관,B\n",
                                        encoding="utf-8-sig")
    out = tmp_path / "o"
    rc = main.run(config.load_settings(["--config", str(tmp_path / "none.json"),
                                        "--input-dir", str(d), "--output-dir", str(out)]))
    assert rc == 0
    assert (out / "box_by_defect.csv").exists() and (out / "box_position_grid.csv").exists()


# ---------------------------------------------------------------- 제공 데이터 검증
def test_provided_data_boxes():
    settings = config.load_settings([])
    if not (Path(settings.input_dir) / "facility_A_log.csv").exists():
        pytest.skip("제공 데이터가 없어 박스 분석 통합 검증을 건너뜀")
    import logging
    import main
    logs = main.load_all_logs(settings, logging.getLogger("test"))
    boxes, invalid = box.compute_boxes(logs, settings.image_width, settings.image_height)
    expected = ((logs["result"] == "NG") & (logs["defect_code"] != "D99")).sum()
    assert len(boxes) + len(invalid) <= expected  # 좌표가 빈 NG 행은 어느 쪽에도 없다
    assert len(boxes) > 0
    assert box.position_grid(boxes, settings.image_width, settings.image_height,
                             settings.box_grid_cols, settings.box_grid_rows)["건수"].sum() == len(boxes) * 2
