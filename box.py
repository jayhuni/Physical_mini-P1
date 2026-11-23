"""불량 박스 분석 (O1).

불량 박스 좌표(box_x1, box_y1, box_x2, box_y2)로 중심점과 면적을 계산하고,
불량 종류별 평균 크기와 사진 안 위치 분포(격자 칸별 건수)를 정리한다.

- 대상: result == NG 이면서 판정 불가(D99)가 아니고 좌표 4개가 모두 있는 기록
- 잘못된 좌표: x2 <= x1, y2 <= y1, 또는 사진(width x height) 밖 -> 분석에서 빼고 따로 돌려준다
- 좌표계: 사진 왼쪽 위가 (0, 0), 오른쪽이 +x, 아래쪽이 +y (px)
"""
from __future__ import annotations

import pandas as pd

from aggregator import DEFECT_RESULT, UNDETERMINABLE_CODE

BOX_COLUMNS = ["box_x1", "box_y1", "box_x2", "box_y2"]
ALL_DEFECTS = "전체"  # 위치 분포 표에서 모든 불량 종류를 합친 행의 이름


def compute_boxes(df: pd.DataFrame, width: int, height: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(정상 박스, 잘못된 좌표 박스)를 돌려준다. 정상 박스에는 중심점·너비·높이·면적 열을 붙인다."""
    has_box = ((df["result"] == DEFECT_RESULT) & (df["defect_code"] != UNDETERMINABLE_CODE)
               & df[BOX_COLUMNS].notna().all(axis=1))
    work = df[has_box]
    x1, y1, x2, y2 = (work[c] for c in BOX_COLUMNS)
    valid = ((x2 > x1) & (y2 > y1) & (x1 >= 0) & (y1 >= 0) & (x2 <= width) & (y2 <= height))

    boxes = work[valid].copy()
    boxes["중심x"] = (boxes["box_x1"] + boxes["box_x2"]) / 2
    boxes["중심y"] = (boxes["box_y1"] + boxes["box_y2"]) / 2
    boxes["너비"] = boxes["box_x2"] - boxes["box_x1"]
    boxes["높이"] = boxes["box_y2"] - boxes["box_y1"]
    boxes["면적"] = boxes["너비"] * boxes["높이"]
    return boxes.reset_index(drop=True), work[~valid].reset_index(drop=True)


def box_by_defect(boxes: pd.DataFrame, width: int, height: int) -> pd.DataFrame:
    """불량 종류별 건수, 평균 너비·높이·면적, 면적 중앙값, 평균 중심점, 사진 대비 면적 비율(%)."""
    out = boxes.groupby(["defect_code", "defect_name"], as_index=False).agg(
        건수=("면적", "size"), 평균너비=("너비", "mean"), 평균높이=("높이", "mean"),
        평균면적=("면적", "mean"), 면적중앙값=("면적", "median"),
        평균중심x=("중심x", "mean"), 평균중심y=("중심y", "mean"))
    out["면적비율(%)"] = out["평균면적"] / (width * height) * 100
    out = out.round(2)
    return out.sort_values(["건수", "defect_code"], ascending=[False, True],
                           kind="mergesort").reset_index(drop=True)


def position_grid(boxes: pd.DataFrame, width: int, height: int, cols: int, rows: int) -> pd.DataFrame:
    """사진을 cols x rows 칸으로 나눠 박스 중심이 들어간 칸별 건수를 센다.

    모든 불량을 합친 '전체' 행과 불량 종류별 행이 있고, 박스가 없는 칸도 0으로 남긴다.
    칸 경계에 정확히 걸친 중심은 오른쪽·아래 칸으로, 사진 끝(width, height)은 마지막 칸으로 센다.
    """
    cell_w, cell_h = width / cols, height / rows
    placed = boxes.assign(
        열=(boxes["중심x"] // cell_w).clip(upper=cols - 1).astype(int),
        행=(boxes["중심y"] // cell_h).clip(upper=rows - 1).astype(int))

    names = [ALL_DEFECTS] + sorted(boxes["defect_name"].dropna().unique())
    cells = pd.MultiIndex.from_product([names, range(rows), range(cols)],
                                       names=["defect_name", "행", "열"])
    per_defect = placed.groupby(["defect_name", "행", "열"]).size()
    overall = placed.groupby(["행", "열"]).size()
    overall.index = pd.MultiIndex.from_tuples([(ALL_DEFECTS, r, c) for r, c in overall.index],
                                              names=["defect_name", "행", "열"])
    counts = pd.concat([overall, per_defect]).reindex(cells, fill_value=0)

    out = counts.rename("건수").reset_index()
    out["x시작"] = (out["열"] * cell_w).round().astype(int)
    out["x끝"] = ((out["열"] + 1) * cell_w).round().astype(int)
    out["y시작"] = (out["행"] * cell_h).round().astype(int)
    out["y끝"] = ((out["행"] + 1) * cell_h).round().astype(int)
    out["건수"] = out["건수"].astype(int)
    return out[["defect_name", "행", "열", "x시작", "x끝", "y시작", "y끝", "건수"]]


def position_matrix(grid: pd.DataFrame, defect_name: str = ALL_DEFECTS) -> pd.DataFrame:
    """position_grid 결과에서 한 불량 종류를 행 x 열 표로 바꾼다 (Dash 히트맵용)."""
    part = grid[grid["defect_name"] == defect_name]
    return part.pivot(index="행", columns="열", values="건수")
