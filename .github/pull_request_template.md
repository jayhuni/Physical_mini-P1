## 무엇을 바꿨나
<!-- 기능 요약. 관련 요구사항 번호(O1, O2 등) -->

## 왜
<!-- 문제와 고른 방법의 이유 -->

## 검증
- [ ] `python -m pytest tests -q` 통과, skipped 0
- [ ] 집계를 바꿨다면 `python main.py` 결과(5,198건 / 불량 238건 / 4.58%) 변화가 의도한 것인지 확인
- [ ] 화면을 바꿨다면 `python app.py`를 띄워 선택을 바꿔 봄

## 협업 체크
- [ ] `bash scripts/sync_check.sh` 결과 충돌 예상 없음 (있었다면 해결 방법을 아래에)
- [ ] 최신 `main`을 merge 했음
- [ ] `docs/devlog/`에 이번 작업 기록 파일 추가
- [ ] AI로 작성한 부분은 `AI_USAGE.md`에 기록
- [ ] `git status`에 `input/`, `output/`의 CSV가 없음

## 겹친 파일 / 충돌 메모
<!-- 없으면 "없음" -->
