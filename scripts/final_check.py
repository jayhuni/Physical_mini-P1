"""제출 전 최종 점검. 제공 데이터(input/)로 테스트·처리·화면 계산을 한 번에 확인한다.

    python scripts/final_check.py

확인 항목
 1) 입력 파일 4개가 있는지
 2) pytest 전체 통과, skipped 0
 3) python main.py 실행 성공, 요약 수치가 과제 제출 때 값(5,198건 / 238건 / 4.58%)과 같은지
 4) O2: 데이터에서 확인된 급증 3건을 찾는지
 5) O1: 박스 분석 결과와 잘못된 좌표 건수
 6) 대시보드 계산(build_view)이 기본·필터·D99 제외 조건에서 오류 없이 도는지
결과는 화면과 output/final_check.txt 에 남긴다. 발표·포트폴리오에 쓸 실제 수치도 함께 출력한다.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

import box  # noqa: E402
import config  # noqa: E402
import main as pipeline  # noqa: E402

# 과제 제출 때 확인한 값 (TEAM_README "PR 전에 확인할 것")
EXPECTED = {"total": 5198, "defects": 238, "defect_rate": 4.58}
# PORTFOLIO "데이터에서 발견한 것": D99 11건(전부 A-CAM1 11/20) -> 제외하면 238 - 11 = 227건, 227/5198 = 4.37%
EXPECTED_EXCL_D99 = {"defects": 227, "defect_rate": 4.37}
# TEAM_README 6절: 데이터에서 눈으로 확인된 급증 (날짜, 시설, 카메라 또는 None, 불량 이름 일부)
KNOWN_SPIKES = [("2026-11-20", "A시설", "A-CAM1", "판정 불가"),
                ("2026-11-19", "C시설", None, "치수"),
                ("2026-11-18", "B시설", None, "이물")]

lines: list[str] = []
failures: list[str] = []


def report(ok: bool, message: str) -> None:
    mark = "OK  " if ok else "FAIL"
    lines.append(f"[{mark}] {message}")
    print(lines[-1])
    if not ok:
        failures.append(message)


def info(message: str) -> None:
    lines.append(f"       {message}")
    print(lines[-1])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import os
    os.chdir(ROOT)
    settings = config.load_settings([])

    # 1) 입력 파일
    in_dir = Path(settings.input_dir)
    needed = [settings.defect_codes_file] + [f"facility_{c}_log.csv" for c in "ABC"]
    missing = [n for n in needed if not (in_dir / n).exists()]
    report(not missing, f"입력 파일 ({in_dir}/): " + ("4개 모두 있음" if not missing else f"없음 {missing}"))
    if missing:
        print("\n제공 데이터를 input/ 폴더에 넣고 다시 실행하세요.")
        return 1

    # 2) 테스트
    r = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    last = (r.stdout.strip().splitlines() or ["(출력 없음)"])[-1]
    report(r.returncode == 0 and "skipped" not in last, f"pytest: {last}")
    if r.returncode != 0:
        for ln in r.stdout.splitlines():
            if ln.startswith("FAILED"):
                info(ln)

    # 3) 전체 처리
    rc = pipeline.run(settings)
    report(rc == 0, f"python main.py 실행 (종료 코드 {rc})")
    out_dir = Path(settings.output_dir)
    logs = pipeline.load_all_logs(settings, logging.getLogger("final_check"))
    import aggregator
    s = aggregator.overall_summary(logs, settings.process_ms_threshold)
    got = {"total": s["total"], "defects": s["defects"], "defect_rate": s["defect_rate"]}
    report(got == EXPECTED, f"요약 수치 {got} (기대 {EXPECTED})")
    d99 = int((logs["defect_code"] == aggregator.UNDETERMINABLE_CODE).sum())
    excl = aggregator.overall_summary(aggregator.apply_d99_policy(logs, False))
    got_excl = {"defects": excl["defects"], "defect_rate": excl["defect_rate"]}
    report(got_excl == EXPECTED_EXCL_D99, f"D99 {d99}건 제외 시 {got_excl} (기대 {EXPECTED_EXCL_D99})")
    info(f"이상 기록 {s['anomalies']}건, 불량률 최고 시설 {s['worst_facility']} ({s['worst_facility_rate']}%)")

    # 4) O2 급증
    spikes = pd.read_csv(out_dir / pipeline.OUT_SPIKES, encoding="utf-8-sig", dtype={"날짜": str})
    for date, fac, cam, name in KNOWN_SPIKES:
        m = (spikes["날짜"] == date) & (spikes["facility"] == fac) & \
            spikes["defect_name"].fillna("").str.contains(name)
        if cam:
            m &= spikes["camera_id"] == cam
        where = f"{fac} {cam}" if cam else fac
        hit = spikes[m]
        detail = (f"{int(hit.iloc[0]['불량수'])}건, 기대 {hit.iloc[0]['기대건수']}건, p={hit.iloc[0]['p값']:.1e}"
                  if len(hit) else "못 찾음")
        report(len(hit) > 0, f"급증 {date} {where} {name}: {detail}")
    known = len(spikes)
    info(f"급증 탐지 전체 {known}건 (시설·카메라 단위 합계). 3건 외의 탐지는 output/spikes.csv에서 실제 이상인지 확인")

    # 5) O1 박스
    boxes, bad = box.compute_boxes(logs, settings.image_width, settings.image_height)
    report(len(boxes) > 0, f"박스 분석: 정상 {len(boxes)}건, 잘못된 좌표 {len(bad)}건")
    by = box.box_by_defect(boxes, settings.image_width, settings.image_height)
    if len(by):
        big = by.sort_values("평균면적", ascending=False).iloc[0]
        small = by.sort_values("평균면적").iloc[0]
        info(f"평균 면적 최대 {big['defect_name']} {big['평균면적']:.0f}px², 최소 {small['defect_name']} {small['평균면적']:.0f}px²")
    grid = box.position_grid(boxes, settings.image_width, settings.image_height,
                             settings.box_grid_cols, settings.box_grid_rows)
    allc = grid[grid["defect_name"] == box.ALL_DEFECTS].sort_values("건수", ascending=False).iloc[0]
    if len(boxes):
        info(f"가장 많이 몰린 칸: x {allc['x시작']}~{allc['x끝']}, y {allc['y시작']}~{allc['y끝']} "
             f"({allc['건수']}건, 전체의 {allc['건수'] / len(boxes) * 100:.1f}%)")

    # 6) 대시보드 계산
    try:
        import app
        for args in [(None, None, None, None, False), (["B시설"], "2026-11-18", "2026-11-18", None, False),
                     (None, None, None, ["이물"], True), (["없는시설"], None, None, None, False)]:
            fac, start, end, defect, excl_d99 = args
            app.build_view(app.LOGS, fac, start, end, defect, settings.process_ms_threshold,
                           app.SPIKES, excl_d99, app.SETTINGS)
        report(True, "대시보드 계산(build_view) 4가지 조건 정상")
    except Exception as exc:  # 화면 계산 오류는 원인을 그대로 보여 준다
        report(False, f"대시보드 계산 오류: {type(exc).__name__}: {exc}")

    print()
    lines.append("")
    verdict = "모든 항목 통과" if not failures else f"실패 {len(failures)}건"
    lines.append(f"결과: {verdict}")
    print(lines[-1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "final_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"기록: {out_dir / 'final_check.txt'}")
    if not failures:
        print("\n남은 확인: python app.py 를 실행해 브라우저에서 선택을 바꿔 본다 (화면 배치는 직접 봐야 한다)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
