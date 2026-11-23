"""급증(O2) 기준값 선정 시뮬레이션. ADR-002의 표를 다시 만든다.

    python scripts/tune_spike.py

제공 데이터와 같은 규모(시설 3, 카메라 5, 5일, 하루 180~270건, 불량률 약 3%)의 포아송 합성 데이터로
1) 급증이 없는 데이터에서 몇 건이 잘못 잡히는지(오탐)
2) 제공 데이터에서 보인 급증 3건과 같은 크기를 심었을 때 몇 건을 찾는지(탐지율)
를 기준값 조합마다 30회씩 측정한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd

import spike
sys.stdout.reconfigure(encoding="utf-8")

def make(seed, plant, d99_base=0.003):
    rng = np.random.default_rng(seed)
    cams = {"A시설":["A-CAM1","A-CAM2"],"B시설":["B-CAM1"],"C시설":["C-CAM1","C-CAM2"]}
    names = {"D01":"스크래치","D02":"찍힘","D03":"이물","D04":"치수 초과","D05":"치수 미달","D06":"조립 누락","D07":"오조립","D99":"판정 불가"}
    rows=[]
    for f,cs in cams.items():
        for cam in cs:
            n = 270 if f=="B시설" else 180
            for d in pd.date_range("2026-11-16", periods=5):
                p = {c:0.03/7 for c in list(names)[:7]}; p["D99"]=d99_base
                if plant:
                    ds=str(d.date())
                    if (f,cam,ds)==("A시설","A-CAM1","2026-11-20"): p["D99"]=11/n
                    if (f,ds)==("C시설","2026-11-19"): p["D04"]=10.5/n
                    if (f,ds)==("B시설","2026-11-18"): p["D03"]=15/n
                cnt = {c: rng.poisson(pc*n) for c,pc in p.items()}
                for c,k in cnt.items():
                    rows += [(d, f, cam, "NG", c, names[c])]*k
                rows += [(d, f, cam, "OK", None, None)]*max(0, n-sum(cnt.values()))
    return pd.DataFrame(rows, columns=["timestamp","facility","camera_id","result","defect_code","defect_name"])

def hits(out):
    day = out["날짜"].astype(str)
    a = ((day=="2026-11-20")&(out.camera_id=="A-CAM1")&(out.defect_code=="D99")).any()
    c = ((day=="2026-11-19")&(out.facility=="C시설")&(out.defect_code=="D04")).any()
    b = ((day=="2026-11-18")&(out.facility=="B시설")&(out.defect_code=="D03")).any()
    return int(a)+int(b)+int(c)

def fp(out):  # 심은 3건 외 탐지 (단위 무관, 같은 칸 중복 제거)
    day = out["날짜"].astype(str)
    planted = (((day=="2026-11-20")&(out.facility=="A시설")&(out.defect_code=="D99"))|
               ((day=="2026-11-19")&(out.facility=="C시설")&(out.defect_code=="D04"))|
               ((day=="2026-11-18")&(out.facility=="B시설")&(out.defect_code=="D03")))
    return (~planted).sum()

grid = [(5,3.0,1e-3),(5,3.0,1e-4),(5,3.0,1e-5),(8,3.0,1e-3),(8,3.0,1e-4),(10,3.0,1e-4)]
SEEDS = range(30)
for mc, r, mp in grid:
    fps=[]; rec=[]; fps_plant=[]
    for s in SEEDS:
        fps.append(len(spike.detect_spikes(make(s, False), mc, r, mp)))
        o = spike.detect_spikes(make(1000+s, True), mc, r, mp)
        rec.append(hits(o)); fps_plant.append(fp(o))
    print(f"min={mc:2d} ratio={r} p<={mp:g}  오탐(무작위)/회 평균 {np.mean(fps):.2f}  "
          f"급증 심은 데이터: 탐지 {np.mean(rec):.2f}/3 (3건 모두 {np.mean(np.array(rec)==3)*100:.0f}%), 그 외 탐지 {np.mean(fps_plant):.2f}")
