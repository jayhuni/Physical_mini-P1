"""제출용 압축 파일 2개를 dist/ 에 만든다 (과제 명세 7절).

    python scripts/make_submission.py

- dist/<폴더명>_code.zip   : 코드. git에 커밋된 파일만 담으므로 제공 데이터(input/)·처리 결과(output/)·
                             가상환경(.venv)이 들어가지 않는다. 커밋 안 된 변경이 있으면 중단한다
- dist/<폴더명>_output.zip : 처리 결과(output/ 폴더). 먼저 python main.py 또는 scripts/final_check.py 를 실행한다
"""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import os
    os.chdir(ROOT)
    settings = config.load_settings([])
    name = ROOT.name
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)

    # 커밋 안 된 변경이 있으면 압축본과 실제 코드가 달라지므로 멈춘다
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True, encoding="utf-8").stdout.strip()
    if dirty:
        print("커밋하지 않은 변경이 있습니다. 커밋한 뒤 다시 실행하세요:\n" + dirty)
        return 1

    code_zip = dist / f"{name}_code.zip"
    subprocess.run(["git", "archive", "--format=zip", f"--prefix={name}/", "-o", str(code_zip), "HEAD"],
                   check=True)
    with zipfile.ZipFile(code_zip) as z:
        names = z.namelist()
    leaked = [n for n in names if n.endswith(".csv") or "/output/" in n or "/input/" in n]
    print(f"코드 압축: {code_zip} ({len(names)}개 항목)")
    if leaked:
        print(f"  경고: 데이터/결과로 보이는 파일이 들어 있습니다: {leaked}")
        return 1

    out_dir = Path(settings.output_dir)
    if not (out_dir / "summary.txt").exists():
        print(f"처리 결과가 없습니다. 먼저 python main.py 를 실행하세요 ({out_dir}/summary.txt 없음)")
        return 1
    out_zip = dist / f"{name}_output.zip"
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out_dir.rglob("*")):
            if f.is_file():
                z.write(f, Path(out_dir.name) / f.relative_to(out_dir))
    with zipfile.ZipFile(out_zip) as z:
        print(f"결과 압축: {out_zip} ({len(z.namelist())}개 파일)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
