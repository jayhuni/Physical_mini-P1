"""전체 처리 실행 파일 (S6).

    python main.py

읽기 -> 합치기 -> 불량코드 결합 -> 집계 -> CSV/그래프/요약 저장을 한 번에 수행한다.
기능 자체는 loader / aggregator / exporter / plotter 모듈에 있고, 이 파일은 순서만 묶는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import aggregator
import config
import exporter
import loader
import plotter
import spike

# 출력 파일 이름 (README의 출력 파일 설명과 같은 이름)
OUT_ALL_LOGS = "all_facility_log.csv"
OUT_FACILITY = "facility_summary.csv"
OUT_DEFECT_BY_FACILITY = "defect_by_facility.csv"
OUT_DEFECT_BY_CATEGORY = "defect_by_category.csv"
OUT_DAILY = "daily_facility_summary.csv"
OUT_CAMERA = "camera_summary.csv"
OUT_ANOMALIES = "anomalies.csv"
OUT_FILTERED = "filtered_logs.csv"
OUT_SUMMARY = "summary.txt"
OUT_CHART_DEFECT = "chart_defect_by_facility.png"
OUT_CHART_DAILY = "chart_daily_defect_rate.png"
OUT_SPIKES = "spikes.csv"


def load_all_logs(settings: config.Settings, logger):
    """시설 로그를 모두 읽어 합치고 불량코드표를 결합한 전체 로그를 돌려준다.

    app.py(Dash)도 이 함수로 앱 시작 시 한 번만 로그를 읽는다 (D7).
    """
    frames = loader.read_facility_logs(settings.input_dir, settings.facility_file_prefix, logger)
    merged = loader.merge_logs(frames)
    codes = loader.load_defect_codes(Path(settings.input_dir) / settings.defect_codes_file)
    return loader.attach_defect_info(merged, codes)


def run(settings: config.Settings) -> int:
    """전체 처리를 실행한다. 성공하면 0, 실패하면 1을 돌려준다."""
    out_dir = exporter.ensure_output_dir(settings.output_dir)  # S3
    logger = exporter.setup_run_logger(out_dir)                # S4
    enc = settings.csv_encoding

    try:
        df = load_all_logs(settings, logger)
    except Exception as exc:  # 읽을 수 있는 입력이 없으면 의미 있는 처리가 불가능하다
        logger.error("처리 중단: %s: %s", type(exc).__name__, exc)
        return 1

    # F2/F3: 전체 시설 로그
    exporter.save_csv(df, out_dir / OUT_ALL_LOGS, enc)

    # F4~F8: 집계 결과
    exporter.save_csv(aggregator.facility_summary(df), out_dir / OUT_FACILITY, enc)
    defect_table = aggregator.defect_by_facility(df)
    exporter.save_csv(defect_table, out_dir / OUT_DEFECT_BY_FACILITY, enc)
    exporter.save_csv(aggregator.defect_by_category(df), out_dir / OUT_DEFECT_BY_CATEGORY, enc)
    daily = aggregator.daily_facility_summary(df)
    exporter.save_csv(daily, out_dir / OUT_DAILY, enc)
    exporter.save_csv(aggregator.camera_summary(df), out_dir / OUT_CAMERA, enc)
    anomalies = aggregator.find_anomalies(df, settings.process_ms_threshold)
    exporter.save_csv(anomalies, out_dir / OUT_ANOMALIES, enc)

    # F9: 조건이 하나라도 주어졌을 때만 필터 결과를 저장한다
    if any([settings.facilities, settings.start_date, settings.end_date, settings.defect_types]):
        picked = aggregator.filter_logs(df, settings.facilities, settings.start_date,
                                        settings.end_date, settings.defect_types)
        exporter.save_csv(picked, out_dir / OUT_FILTERED, enc)
        logger.info("조건 필터 결과 %d건 저장: %s", len(picked), OUT_FILTERED)

    # O2: 불량 급증 탐지 (기준은 config의 spike_* 값, 설명은 ADR-002)
    spikes = spike.detect_spikes(df, settings.spike_min_count, settings.spike_ratio,
                                 settings.spike_max_p)
    exporter.save_csv(spikes, out_dir / OUT_SPIKES, enc)
    logger.info("불량 급증 %d건 탐지: %s", len(spikes), OUT_SPIKES)

    # F10: 그래프
    plotter.plot_defect_by_facility(defect_table, out_dir / OUT_CHART_DEFECT)
    plotter.plot_daily_defect_rate(daily, out_dir / OUT_CHART_DAILY)

    # F11: 요약 (파일 저장 + 화면 출력)
    summary_text = aggregator.format_summary_text(
        aggregator.overall_summary(df, settings.process_ms_threshold))
    summary_text += "\n" + spike.format_spike_text(spikes)  # O2 결과를 요약 끝에 붙인다
    exporter.save_text(summary_text, out_dir / OUT_SUMMARY)
    print(summary_text)
    logger.info("처리 완료. 결과 폴더: %s", out_dir.resolve())
    return 0


if __name__ == "__main__":
    # 화면 출력에서 한글이 깨지지 않도록 표준 출력 인코딩을 UTF-8로 맞춘다 (Windows 콘솔 대비)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(run(config.load_settings()))
