"""Dash 화면 (D1~D7).

    python app.py   ->   웹 브라우저에서 http://127.0.0.1:8050 접속

집계는 모두 aggregator.py 의 함수를 호출해서 하고, 이 파일에는 집계 코드를 두지 않는다 (D7).
로그는 앱을 시작할 때 한 번만 읽고, 선택이 바뀔 때마다 메모리의 DataFrame을 다시 걸러 쓴다.
"""
from __future__ import annotations

import logging
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html

import aggregator
import box
import config
import main as pipeline
import spike

logger = logging.getLogger("vision_app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ------------------------------------------------------------------ 시작 시 한 번만 로그 읽기 (D7)
# python app.py 로 직접 실행했을 때만 명령 인자를 읽는다 (import 되는 경우 pytest 등의 인자와 충돌 방지)
SETTINGS = config.load_settings(sys.argv[1:] if __name__ == "__main__" else [])
LOGS = pipeline.load_all_logs(SETTINGS, logger)

FACILITY_OPTIONS = sorted(LOGS["facility"].unique())
# 불량 종류 선택지: 실제 불량 기록에 나온 이름만 코드 순서로 보여 준다
DEFECT_OPTIONS = (
    LOGS.loc[LOGS["result"] == aggregator.DEFECT_RESULT, ["defect_code", "defect_name"]]
    .drop_duplicates().sort_values("defect_code")["defect_name"].tolist()
)
# O2 급증은 전체 기간을 '평소'로 삼아 시작할 때 한 번만 계산하고, 화면에서는 조건으로 고르기만 한다
SPIKES = spike.detect_spikes(LOGS, SETTINGS.spike_min_count, SETTINGS.spike_ratio, SETTINGS.spike_max_p)
MIN_DATE = LOGS["timestamp"].min().date()
MAX_DATE = LOGS["timestamp"].max().date()

# 이상 기록 표에 보여 줄 열 (전체 열은 너무 넓다)
ANOMALY_COLUMNS = ["timestamp", "facility", "camera_id", "serial_no", "defect_name",
                   "process_ms", "reason"]


def empty_figure(message: str) -> go.Figure:
    """선택 조건에 맞는 데이터가 없을 때 보여 줄 빈 그래프."""
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font={"size": 16})
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def build_view(df: pd.DataFrame, facilities, start_date, end_date, defect_types,
               threshold_ms: float, spikes: pd.DataFrame | None = None,
               exclude_d99: bool = False, settings: config.Settings | None = None) -> dict:
    """선택 조건으로 화면에 보여 줄 모든 값을 계산한다.

    Dash 콜백과 분리한 순수 함수라 브라우저 없이 테스트할 수 있다.
    시설·날짜는 검사 대상(모집단)을 정하고, 불량 종류는 불량으로 셀 종류만 정한다.
    """
    # D99를 불량에서 뺄지 (이상 기록은 불량 코드로 판단하므로 영향 없음, 급증 목록은 원본 기준)
    df = aggregator.apply_d99_policy(df, count_d99_as_defect=not exclude_d99)
    base = aggregator.filter_logs(df, facilities, start_date, end_date)
    summary = aggregator.overall_summary(base, threshold_ms, defect_types)
    # O2: 급증 목록은 선택한 시설·날짜·불량 종류로 고르기만 한다 (평소 기준은 전체 기간)
    if spikes is None:
        spikes = spike.detect_spikes(df)
    picked_spikes = spike.select_spikes(spikes, facilities, start_date, end_date, defect_types)
    picked_spikes = picked_spikes.astype({"날짜": str, "배수": object}).fillna({"camera_id": "-", "배수": "평소 0건"})
    picked_spikes["p값"] = picked_spikes["p값"].map(lambda v: f"{v:.1e}")  # 표시용 서식 (CSV는 원래 값)
    # O1: 선택한 시설·날짜·불량 종류의 불량 박스 분석
    box_view = build_box_view(aggregator.filter_logs(base, defect_types=defect_types),
                              settings or config.Settings())

    if base.empty:  # 선택 조건에 맞는 기록이 없는 경우
        msg = "선택한 조건에 맞는 기록이 없습니다"
        return {"summary": summary, "bar": empty_figure(msg), "line": empty_figure(msg),
                "table": pd.DataFrame(), "anomalies": pd.DataFrame(columns=ANOMALY_COLUMNS),
                "spikes": picked_spikes, **box_view}

    # D4 막대그래프: 시설별 불량 종류 건수 (표를 그래프용 긴 형태로 바꾼다)
    table = aggregator.defect_by_facility(base, defect_types)
    long = table.melt(id_vars="facility", var_name="불량 종류", value_name="건수")
    if long.empty or long["건수"].sum() == 0:
        bar = empty_figure("선택한 조건에 해당하는 불량이 없습니다")
    else:
        bar = px.bar(long, x="불량 종류", y="건수", color="facility", barmode="group",
                     labels={"facility": "시설"}, title="시설별 불량 종류 건수")

    # D4 꺾은선그래프: 날짜별 불량률 추이
    daily = aggregator.daily_facility_summary(base, defect_types)
    daily["date"] = daily["date"].astype(str)
    line = px.line(daily, x="date", y="불량률(%)", color="facility", markers=True,
                   labels={"date": "검사 날짜", "facility": "시설"}, title="날짜별 시설 불량률 추이")

    # D5 이상 기록: 선택한 시설·날짜 안에서, 불량 종류를 골랐다면 그 종류만
    anomalies = aggregator.find_anomalies(base, threshold_ms)
    if defect_types:
        anomalies = aggregator.filter_logs(anomalies, defect_types=defect_types)
    anomalies = anomalies.reindex(columns=ANOMALY_COLUMNS)
    anomalies["timestamp"] = anomalies["timestamp"].astype(str)
    summary["anomalies"] = len(anomalies)  # 요약 카드의 이상 기록 수를 아래 표의 행 수와 일치시킨다

    return {"summary": summary, "bar": bar, "line": line, "table": table, "anomalies": anomalies,
            "spikes": picked_spikes, **box_view}


def build_box_view(df: pd.DataFrame, s: config.Settings) -> dict:
    """O1 화면 요소: 불량 종류별 박스 크기 표, 위치 분포 히트맵, 중심점 산점도. 계산은 box.py가 한다."""
    w, h = s.image_width, s.image_height
    boxes, _ = box.compute_boxes(df, w, h)
    table = box.box_by_defect(boxes, w, h)
    if boxes.empty:
        msg = "선택한 조건에 해당하는 불량 박스가 없습니다"
        return {"box_table": table, "box_heatmap": empty_figure(msg), "box_scatter": empty_figure(msg)}

    grid = box.position_grid(boxes, w, h, s.box_grid_cols, s.box_grid_rows)
    matrix = box.position_matrix(grid)
    cells = grid[grid["defect_name"] == box.ALL_DEFECTS]
    x_labels = [f"{a}~{b}" for a, b in cells[cells["행"] == 0][["x시작", "x끝"]].itertuples(index=False)]
    y_labels = [f"{a}~{b}" for a, b in cells[cells["열"] == 0][["y시작", "y끝"]].itertuples(index=False)]
    heatmap = go.Figure(go.Heatmap(z=matrix.to_numpy(), x=x_labels, y=y_labels, colorscale="Reds",
                                   texttemplate="%{z}", hovertemplate="x %{x}, y %{y}: %{z}건<extra></extra>"))
    heatmap.update_layout(title="사진 안 불량 위치 분포 (박스 중심, 칸별 건수)",
                          xaxis_title="x (px)", yaxis_title="y (px)")
    heatmap.update_yaxes(autorange="reversed")  # 사진 좌표: 위쪽이 y=0

    scatter = px.scatter(boxes, x="중심x", y="중심y", color="defect_name", size="면적", size_max=14,
                         hover_data=["facility", "camera_id", "serial_no", "너비", "높이"],
                         labels={"defect_name": "불량 종류"}, title="불량 박스 중심점 (크기 = 면적)")
    scatter.update_xaxes(range=[0, w])
    scatter.update_yaxes(range=[h, 0], scaleanchor="x")  # 위쪽이 y=0, 가로세로 비율 유지
    return {"box_table": table, "box_heatmap": heatmap, "box_scatter": scatter}


def summary_card(label: str, value: str) -> html.Div:
    """요약 숫자 카드 한 개."""
    return html.Div(
        [html.Div(label, style={"color": "#666", "fontSize": "14px"}),
         html.Div(value, style={"fontSize": "30px", "fontWeight": "bold"})],
        style={"border": "1px solid #ddd", "borderRadius": "8px", "padding": "12px 24px",
               "minWidth": "160px", "textAlign": "center"})


def make_table(df: pd.DataFrame, table_id: str) -> dash_table.DataTable:
    """DataFrame을 화면 표로 만든다."""
    return dash_table.DataTable(
        id=table_id, data=df.to_dict("records"),
        columns=[{"name": str(c), "id": str(c)} for c in df.columns],
        page_size=10, sort_action="native",
        style_table={"overflowX": "auto"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f3f3f3"},
        style_cell={"textAlign": "center", "padding": "6px"})


# ------------------------------------------------------------------ 화면 구성 (D2)
app = Dash(__name__)
app.title = "비전검사 로그 대시보드"

app.layout = html.Div(
    style={"maxWidth": "1200px", "margin": "0 auto", "padding": "16px",
           "fontFamily": "'Malgun Gothic', sans-serif"},
    children=[
        html.H2("비전검사 로그 대시보드"),
        # 위쪽 선택 요소: 시설(다중), 날짜 범위, 불량 종류
        html.Div(style={"display": "flex", "gap": "24px", "flexWrap": "wrap", "marginBottom": "16px"},
                 children=[
            html.Div([html.Label("시설 (여러 개 선택 가능)"),
                      dcc.Dropdown(id="facility", options=FACILITY_OPTIONS, multi=True,
                                   placeholder="전체 시설", style={"width": "280px"})]),
            html.Div([html.Label("날짜 범위"), html.Br(),
                      dcc.DatePickerRange(id="dates", min_date_allowed=MIN_DATE, max_date_allowed=MAX_DATE,
                                          start_date=MIN_DATE, end_date=MAX_DATE,
                                          display_format="YYYY-MM-DD")]),
            html.Div([html.Label("불량 종류"),
                      dcc.Dropdown(id="defect", options=DEFECT_OPTIONS, multi=True,
                                   placeholder="전체 불량 종류", style={"width": "320px"})]),
            html.Div([html.Label("불량률 기준"),
                      dcc.Checklist(id="d99", options=[{"label": " 판정 불가(D99)를 불량에서 제외",
                                                         "value": "exclude"}],
                                    value=[] if SETTINGS.count_d99_as_defect else ["exclude"])]),
        ]),
        html.Div(id="summary", style={"display": "flex", "gap": "16px", "flexWrap": "wrap",
                                      "marginBottom": "16px"}),
        html.Div(style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}, children=[
            html.Div(dcc.Graph(id="bar"), style={"flex": "1 1 480px"}),
            html.Div(dcc.Graph(id="line"), style={"flex": "1 1 480px"}),
        ]),
        html.H4("시설 × 불량 종류 건수"),
        html.Div(id="table"),
        html.H4("이상 기록 목록 (판정 불가 또는 처리 시간 초과)"),
        html.Div(id="anomalies"),
        html.H4(f"불량 급증 탐지 (O2: 평소 기대 건수의 {SETTINGS.spike_ratio:g}배 이상, "
                f"{SETTINGS.spike_min_count}건 이상, 우연 확률 p ≤ {SETTINGS.spike_max_p:g})"),
        html.Div(id="spikes"),
        html.H4("불량 박스 분석 (O1: 판정 불가·좌표 없는 기록 제외)"),
        html.Div(id="box-table"),
        html.Div(style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}, children=[
            html.Div(dcc.Graph(id="box-heatmap"), style={"flex": "1 1 480px"}),
            html.Div(dcc.Graph(id="box-scatter"), style={"flex": "1 1 480px"}),
        ]),
    ])


# ------------------------------------------------------------------ 선택이 바뀌면 전부 다시 계산 (D6)
@app.callback(
    Output("summary", "children"), Output("bar", "figure"), Output("line", "figure"),
    Output("table", "children"), Output("anomalies", "children"), Output("spikes", "children"),
    Output("box-table", "children"), Output("box-heatmap", "figure"), Output("box-scatter", "figure"),
    Input("facility", "value"), Input("dates", "start_date"), Input("dates", "end_date"),
    Input("defect", "value"), Input("d99", "value"))
def update(facilities, start_date, end_date, defect_types, d99=None):
    view = build_view(LOGS, facilities, start_date, end_date, defect_types,
                      SETTINGS.process_ms_threshold, SPIKES, exclude_d99="exclude" in (d99 or []),
                      settings=SETTINGS)
    s = view["summary"]
    cards = [summary_card("검사 수", f"{s['total']:,}"),
             summary_card("불량 수", f"{s['defects']:,}"),
             summary_card("불량률", f"{s['defect_rate']:.2f}%"),
             summary_card("이상 기록", f"{s['anomalies']:,}")]
    return (cards, view["bar"], view["line"],
            make_table(view["table"], "t-defect"), make_table(view["anomalies"], "t-anomaly"),
            make_table(view["spikes"], "t-spike"),
            make_table(view["box_table"], "t-box"), view["box_heatmap"], view["box_scatter"])


if __name__ == "__main__":
    app.run(debug=False)
