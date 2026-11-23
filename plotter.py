"""그래프 모듈 (F10).

matplotlib으로 PNG 그래프를 만든다. 제목, 축 이름, 범례의 한글이 깨지지 않도록
설치된 한글 글꼴을 찾아 지정한다.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 화면 없이 파일로만 저장하는 백엔드 (서버/Dash 환경에서도 안전)
import matplotlib.pyplot as plt
from matplotlib import font_manager

# OS별로 흔한 한글 글꼴을 우선순위대로 나열한다
KOREAN_FONT_CANDIDATES = [
    "Malgun Gothic",      # Windows
    "AppleGothic",        # macOS
    "NanumGothic",        # Linux (나눔 글꼴 설치 시)
    "Noto Sans CJK KR",
    "Noto Sans KR",
    "Gulim",
]


def setup_korean_font() -> str | None:
    """설치된 한글 글꼴을 찾아 matplotlib 기본 글꼴로 지정하고 이름을 돌려준다.

    한글 글꼴이 하나도 없으면 None. 이 경우 한글이 네모(□)로 보일 수 있다.
    """
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in KOREAN_FONT_CANDIDATES:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    else:
        name = None
    # 한글 글꼴은 유니코드 마이너스(−) 기호가 없는 경우가 많아 '-'로 대체한다
    plt.rcParams["axes.unicode_minus"] = False
    return name


def plot_defect_by_facility(table, path: str | Path) -> Path:
    """시설별 불량 종류 건수 묶음 막대그래프를 PNG로 저장한다.

    table: aggregator.defect_by_facility() 결과 (facility 열 + 불량 종류별 건수 열)
    """
    setup_korean_font()
    defect_names = [c for c in table.columns if c != "facility"]
    facilities = list(table["facility"])

    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.8 / max(len(facilities), 1)  # 시설 수에 맞춰 막대 폭을 나눈다
    for i, fac in enumerate(facilities):
        values = table.loc[table["facility"] == fac, defect_names].iloc[0].tolist()
        positions = [x + i * width for x in range(len(defect_names))]
        ax.bar(positions, values, width=width, label=fac)

    # 묶음의 가운데에 불량 종류 이름 눈금을 둔다
    ax.set_xticks([x + width * (len(facilities) - 1) / 2 for x in range(len(defect_names))])
    ax.set_xticklabels(defect_names)
    ax.set_title("시설별 불량 종류 건수")
    ax.set_xlabel("불량 종류")
    ax.set_ylabel("불량 건수")
    ax.legend(title="시설")
    ax.grid(axis="y", alpha=0.3)
    return _save(fig, path)


def plot_daily_defect_rate(daily, path: str | Path) -> Path:
    """날짜별 시설 불량률 추이 꺾은선그래프를 PNG로 저장한다.

    daily: aggregator.daily_facility_summary() 결과 (date, facility, 불량률(%) 열)
    """
    setup_korean_font()
    fig, ax = plt.subplots(figsize=(10, 6))
    for fac, part in daily.groupby("facility"):
        part = part.sort_values("date")
        ax.plot([str(d) for d in part["date"]], part["불량률(%)"], marker="o", label=fac)

    ax.set_title("날짜별 시설 불량률 추이")
    ax.set_xlabel("검사 날짜")
    ax.set_ylabel("불량률 (%)")
    ax.legend(title="시설")
    ax.grid(alpha=0.3)
    return _save(fig, path)


def _save(fig, path: str | Path) -> Path:
    """그림을 PNG로 저장하고 메모리를 해제한다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)  # 닫지 않으면 여러 번 호출할 때 메모리가 쌓인다
    return path
