"""불량 급증 자동 탐지 (O2).

판단 기준 (자세한 이유는 docs/decisions/ADR-002-spike-criterion.md):
같은 단위(시설 또는 카메라)·같은 불량 종류에서, 그날을 뺀 나머지 날의 불량률을 '평소'로 삼는다.
평소 불량률 x 그날 검사 수 = 기대 건수. 아래 세 조건을 모두 만족하면 급증이다.

  1) 그날 불량 수 >= 최소 건수 (기본 5)       : 한두 건 차이로 울리는 것을 막는다
  2) 그날 불량 수 >= 기대 건수 x 배수 (기본 3) : 평소보다 '크게' 늘었는지
  3) 포아송 우연 확률 p <= 기준 (기본 0.0001)  : 평소 수준에서 우연히 나올 확률이 아주 낮은지

건수가 아니라 불량률로 비교하므로, 검사를 많이 한 날 불량이 비례해 늘어난 것은 급증이 아니다.
불량 정의는 aggregator와 같다 (result == NG, D99 포함).
"""
from __future__ import annotations

import math

import pandas as pd

from aggregator import DEFECT_RESULT

# 탐지 단위: 이름 -> 묶는 열. 시설 단위는 카메라 여러 대에 흩어진 급증을, 카메라 단위는 한 대의 이상을 찾는다
LEVELS = {"시설": ["facility"], "카메라": ["facility", "camera_id"]}

COLUMNS = ["단위", "날짜", "facility", "camera_id", "defect_code", "defect_name",
           "검사수", "불량수", "기대건수", "배수", "당일불량률(%)", "평소불량률(%)", "p값"]


def _poisson_upper_tail(count: int, expected: float) -> float:
    """평균 expected인 포아송 분포에서 count건 이상이 나올 확률 P(X >= count).

    scipy 없이 계산한다. 이 데이터의 건수는 수십 건 이하라 직접 더해도 충분하다.
    """
    if count <= 0:
        return 1.0
    if expected <= 0:
        return 0.0  # 평소 0건이면 1건 이상은 '우연'으로 설명할 수 없다
    below = sum(math.exp(-expected + k * math.log(expected) - math.lgamma(k + 1))
                for k in range(count))
    return max(0.0, 1.0 - below)


def _detect_level(df: pd.DataFrame, keys: list[str], min_count: int, ratio: float,
                  max_p: float) -> pd.DataFrame:
    """한 단위(keys)에 대해 날짜·불량 종류별 급증을 찾는다."""
    work = df.assign(날짜=df["timestamp"].dt.date)
    day_keys = ["날짜", *keys]

    # 날짜·단위별 검사 수 (분모)
    inspected = work.groupby(day_keys, as_index=False).agg(검사수=("result", "size"))

    ng = work[work["result"] == DEFECT_RESULT]
    if ng.empty:
        return pd.DataFrame(columns=COLUMNS)
    codes = ng[["defect_code", "defect_name"]].drop_duplicates()
    counted = ng.groupby([*day_keys, "defect_code"], as_index=False).agg(불량수=("result", "size"))

    # 불량이 0건인 날도 '평소'에 들어가야 하므로 (검사한 날 x 불량 종류) 전체 칸을 만든다
    grid = (inspected.merge(codes, how="cross")
            .merge(counted, on=[*day_keys, "defect_code"], how="left"))
    grid["불량수"] = grid["불량수"].fillna(0).astype(int)

    # 그날을 뺀 나머지 날의 합계 = 전체 합계 - 그날 값
    totals = grid.groupby([*keys, "defect_code"])[["검사수", "불량수"]].transform("sum")
    other_n = totals["검사수"] - grid["검사수"]
    other_ng = totals["불량수"] - grid["불량수"]
    has_baseline = other_n > 0  # 비교할 다른 날이 없으면 판단하지 않는다

    base_rate = (other_ng / other_n).where(has_baseline)
    grid["기대건수"] = base_rate * grid["검사수"]
    grid["p값"] = [_poisson_upper_tail(c, e) if pd.notna(e) else 1.0
                  for c, e in zip(grid["불량수"], grid["기대건수"])]

    is_spike = (has_baseline
                & (grid["불량수"] >= min_count)
                & (grid["불량수"] >= ratio * grid["기대건수"])
                & (grid["p값"] <= max_p))
    out = grid[is_spike].copy()
    base_rate = base_rate[is_spike]

    # 평소 0건이면 배수를 정의할 수 없어 빈칸(NaN)으로 둔다
    out["배수"] = (out["불량수"] / out["기대건수"]).where(out["기대건수"] > 0).round(1)
    out["기대건수"] = out["기대건수"].round(2)
    out["당일불량률(%)"] = (out["불량수"] / out["검사수"] * 100).round(2)
    out["평소불량률(%)"] = (base_rate * 100).round(2)
    out["단위"] = next(name for name, k in LEVELS.items() if k == keys)
    return out.reindex(columns=COLUMNS)


def detect_spikes(df: pd.DataFrame, min_count: int = 5, ratio: float = 3.0,
                  max_p: float = 0.0001) -> pd.DataFrame:
    """시설 단위와 카메라 단위의 불량 급증 목록. 우연 확률(p값)이 낮은 순으로 정렬한다."""
    frames = [_detect_level(df, keys, min_count, ratio, max_p) for keys in LEVELS.values()]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["p값", "날짜", "단위"], kind="mergesort").reset_index(drop=True)


def select_spikes(spikes: pd.DataFrame, facilities=None, start_date=None, end_date=None,
                  defect_types=None) -> pd.DataFrame:
    """급증 목록을 시설, 날짜 범위(양 끝 포함), 불량 종류(코드 또는 이름)로 고른다. Dash 화면용."""
    mask = pd.Series(True, index=spikes.index)
    if facilities:
        mask &= spikes["facility"].isin(list(facilities))
    if start_date is not None:
        mask &= spikes["날짜"] >= pd.Timestamp(start_date).date()
    if end_date is not None:
        mask &= spikes["날짜"] <= pd.Timestamp(end_date).date()
    if defect_types:
        wanted = list(defect_types)
        mask &= spikes["defect_code"].isin(wanted) | spikes["defect_name"].isin(wanted)
    return spikes[mask].reset_index(drop=True)


def format_spike_text(spikes: pd.DataFrame) -> str:
    """요약 파일(summary.txt)과 화면 출력에 붙일 급증 보고 텍스트."""
    if spikes.empty:
        return "불량 급증 탐지      : 없음"
    lines = [f"불량 급증 탐지      : {len(spikes)}건 (평소 대비 기준은 README 참고)"]
    for r in spikes.to_dict("records"):
        where = r["facility"] if pd.isna(r["camera_id"]) else f"{r['facility']} {r['camera_id']}"
        times = "평소 0건" if pd.isna(r["배수"]) else f"{r['배수']}배"
        lines.append(f"  - {r['날짜']} [{r['단위']}] {where} {r['defect_name']}: {r['불량수']}건 "
                     f"(기대 {r['기대건수']}건, {times}, "
                     f"불량률 {r['당일불량률(%)']}% / 평소 {r['평소불량률(%)']}%)")
    return "\n".join(lines)
