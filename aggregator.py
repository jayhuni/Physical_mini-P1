"""집계 모듈 (F4~F9, F11).

모든 함수는 loader.attach_defect_info() 까지 거친 전체 로그 DataFrame을 받는다.
Dash 화면(app.py)도 집계를 직접 하지 않고 이 모듈의 함수를 호출한다 (D7).

불량 기준: result == "NG" 인 기록. 판정 불가(D99)도 result가 NG로 기록되므로
불량 수에 포함한다. 단, 이상 기록(F8)에서는 별도로 표시한다.
"""
from __future__ import annotations

import pandas as pd

DEFECT_RESULT = "NG"
UNDETERMINABLE_CODE = "D99"  # 판정 불가
UNDETERMINED_RESULT = "UNDETERMINED"  # D99를 불량에서 뺄 때 쓰는 판정 값 (원본 로그에는 없는 값)


def _rate(defects, total):
    """불량률(%)을 소수 둘째 자리까지 계산한다. 검사 수가 0이면 0.0."""
    return (defects / total * 100).where(total > 0, 0.0).round(2)


def apply_d99_policy(df: pd.DataFrame, count_d99_as_defect: bool = True) -> pd.DataFrame:
    """판정 불가(D99)를 불량으로 셀지 정한 로그를 돌려준다.

    True(기본)면 그대로 돌려준다. False면 D99 기록의 result를 UNDETERMINED로 바꾼 복사본을 돌려준다.
    - 검사 수(분모)에는 남는다: 검사는 수행했기 때문
    - 불량 수(분자)에서는 빠진다: 불량이라고 판정한 것이 아니기 때문
    - 이상 기록(F8)은 불량 코드로 판단하므로 그대로 잡힌다
    원본 df는 바꾸지 않는다.
    """
    if count_d99_as_defect:
        return df
    is_d99 = df["defect_code"] == UNDETERMINABLE_CODE
    return df.assign(result=df["result"].where(~is_d99, UNDETERMINED_RESULT))


def _is_defect(df: pd.DataFrame, defect_types=None) -> pd.Series:
    """불량으로 셀 기록인지 나타내는 True/False 열.

    defect_types를 주면 그 종류(불량 코드 또는 이름)만 불량으로 센다.
    검사 수(분모)는 그대로 두고 불량 수(분자)만 줄이므로 불량률이 의미를 잃지 않는다.
    """
    is_ng = df["result"] == DEFECT_RESULT
    if defect_types:
        wanted = list(defect_types)
        is_ng &= df["defect_code"].isin(wanted) | df["defect_name"].isin(wanted)
    return is_ng


def _count_table(df: pd.DataFrame, keys: list[str], defect_types=None) -> pd.DataFrame:
    """keys 단위로 검사 수, 불량 수, 불량률(%)을 계산하는 공통 함수."""
    is_ng = _is_defect(df, defect_types)
    grouped = (
        df.assign(_ng=is_ng)
        .groupby(keys, as_index=False)
        .agg(검사수=("result", "size"), 불량수=("_ng", "sum"))
    )
    grouped["불량수"] = grouped["불량수"].astype(int)
    grouped["불량률(%)"] = _rate(grouped["불량수"], grouped["검사수"])
    return grouped


# ---------------------------------------------------------------- F4
def facility_summary(df: pd.DataFrame, defect_types=None) -> pd.DataFrame:
    """시설별 검사 수, 불량 수, 불량률(%) (F4)."""
    return _count_table(df, ["facility"], defect_types)


# ---------------------------------------------------------------- F5
def defect_by_facility(df: pd.DataFrame, defect_types=None) -> pd.DataFrame:
    """시설 × 불량 종류 건수 표 (F5). 값이 없는 칸은 0으로 채운다."""
    ng = df[_is_defect(df, defect_types)]
    table = ng.pivot_table(index="facility", columns="defect_name",
                           values="result", aggfunc="size", fill_value=0)
    # 불량이 하나도 없는 시설도 행에 남긴다
    table = table.reindex(sorted(df["facility"].unique()), fill_value=0)
    table.columns.name = None
    return table.reset_index()


def defect_by_category(df: pd.DataFrame, defect_types=None) -> pd.DataFrame:
    """불량 분류(외관, 치수, 조립, 시스템)별 건수 표 (F5)."""
    ng = df[_is_defect(df, defect_types)]
    out = ng.groupby("category", as_index=False).agg(건수=("result", "size"))
    return out.sort_values("건수", ascending=False, kind="mergesort").reset_index(drop=True)


# ---------------------------------------------------------------- F6
def daily_facility_summary(df: pd.DataFrame, defect_types=None) -> pd.DataFrame:
    """날짜별·시설별 검사 수와 불량률 (F6)."""
    work = df.assign(date=df["timestamp"].dt.date)
    return _count_table(work, ["date", "facility"], defect_types)


# ---------------------------------------------------------------- F7
def camera_summary(df: pd.DataFrame, defect_types=None) -> pd.DataFrame:
    """카메라별 검사 수와 불량률 (F7)."""
    return _count_table(df, ["facility", "camera_id"], defect_types)


# ---------------------------------------------------------------- F8
def find_anomalies(df: pd.DataFrame, threshold_ms: float = 1000.0) -> pd.DataFrame:
    """판정 불가(D99)이거나 처리 시간이 기준값을 넘는 기록 목록 (F8).

    '기준값을 넘는'은 초과(>)로 해석한다. 정확히 기준값인 기록은 포함하지 않는다.
    이상 사유(reason) 열을 붙여 어떤 조건에 걸렸는지 알 수 있게 한다.
    """
    undetermined = df["defect_code"] == UNDETERMINABLE_CODE
    slow = df["process_ms"] > threshold_ms
    out = df[undetermined | slow].copy()

    def reason(r) -> str:
        parts = []
        if r["defect_code"] == UNDETERMINABLE_CODE:
            parts.append("판정 불가")
        if r["process_ms"] > threshold_ms:
            parts.append("처리 시간 초과")
        return ", ".join(parts)

    out["reason"] = out.apply(reason, axis=1) if len(out) else pd.Series(dtype=str)
    return out.reset_index(drop=True)


# ---------------------------------------------------------------- F9
def filter_logs(df: pd.DataFrame, facilities=None, start_date=None, end_date=None,
                defect_types=None) -> pd.DataFrame:
    """시설, 날짜 범위, 불량 종류로 기록을 고른다 (F9).

    조건은 일부만 줘도 되고, None이거나 비어 있으면 그 조건은 적용하지 않는다.
    - start_date / end_date: 양 끝 날짜를 포함한다 (end_date는 그날 24시까지)
    - defect_types: 불량 코드(D01)나 불량 이름(스크래치) 어느 쪽으로 줘도 된다
    """
    mask = pd.Series(True, index=df.index)
    if facilities:
        mask &= df["facility"].isin(list(facilities))
    if start_date is not None:
        mask &= df["timestamp"] >= pd.Timestamp(start_date).normalize()
    if end_date is not None:
        # 끝 날짜의 하루 전체를 포함하기 위해 다음 날 0시 미만으로 비교한다
        mask &= df["timestamp"] < pd.Timestamp(end_date).normalize() + pd.Timedelta(days=1)
    if defect_types:
        wanted = list(defect_types)
        mask &= df["defect_code"].isin(wanted) | df["defect_name"].isin(wanted)
    return df[mask].reset_index(drop=True)


# ---------------------------------------------------------------- F11
def overall_summary(df: pd.DataFrame, threshold_ms: float = 1000.0, defect_types=None) -> dict:
    """전체 요약 값을 딕셔너리로 돌려준다 (F11, Dash 요약 숫자(D3)에도 사용)."""
    total = len(df)
    is_ng = _is_defect(df, defect_types)
    defects = int(is_ng.sum())
    summary = {
        "total": total,
        "defects": defects,
        "defect_rate": round(defects / total * 100, 2) if total else 0.0,
        "worst_facility": None,
        "worst_facility_rate": None,
        "top_defect": None,
        "top_defect_count": None,
        "anomalies": len(find_anomalies(df, threshold_ms)),
    }
    if total:
        fac = facility_summary(df, defect_types).sort_values("불량률(%)", ascending=False, kind="mergesort")
        summary["worst_facility"] = fac.iloc[0]["facility"]
        summary["worst_facility_rate"] = float(fac.iloc[0]["불량률(%)"])
    counts = df.loc[is_ng, "defect_name"].value_counts()
    if len(counts):
        summary["top_defect"] = counts.index[0]
        summary["top_defect_count"] = int(counts.iloc[0])
    return summary


def format_summary_text(summary: dict) -> str:
    """요약 딕셔너리를 사람이 읽는 텍스트로 만든다 (F11). 파일 저장과 화면 출력에 같이 쓴다."""
    lines = [
        "===== 비전검사 로그 요약 =====",
        f"전체 검사 수      : {summary['total']:,}건",
        f"전체 불량 수      : {summary['defects']:,}건",
        f"전체 불량률       : {summary['defect_rate']:.2f}%",
    ]
    if summary["worst_facility"] is not None:
        lines.append(f"불량률 최고 시설  : {summary['worst_facility']} ({summary['worst_facility_rate']:.2f}%)")
    else:
        lines.append("불량률 최고 시설  : 해당 없음")
    if summary["top_defect"] is not None:
        lines.append(f"최다 불량 종류    : {summary['top_defect']} ({summary['top_defect_count']:,}건)")
    else:
        lines.append("최다 불량 종류    : 해당 없음")
    lines.append(f"이상 기록 수      : {summary['anomalies']:,}건")
    return "\n".join(lines)
