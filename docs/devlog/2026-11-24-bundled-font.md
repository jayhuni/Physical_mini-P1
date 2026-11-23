# 2026-11-24 한글 글꼴 동봉

- 작성자: jangjunseo05 (Claude Code와 작업)
- 브랜치 / PR: `feat/bundled-korean-font`
- 관련 요구사항: F10 (그래프 한글이 깨지지 않을 것), TEAM_README 남은 작업

## 문제
그래프는 설치된 한글 글꼴(맑은 고딕, AppleGothic 등)을 찾아 썼다. 글꼴이 없는 PC(예: 기본 Linux 서버, 채점 환경)에서는 PNG의 한글이 네모(□)로 나와 F10을 어긴다.

## 판단
- 시스템 글꼴을 **우선** 쓰고, 하나도 없을 때만 동봉 글꼴을 쓴다. 기존 PC의 결과물 모양이 바뀌지 않는다.
- 동봉 글꼴은 나눔고딕(2MB, SIL OFL 1.1). OFL은 소프트웨어와 함께 배포를 허용한다. 라이선스 원문을 같이 넣었다.
- 버린 방법: 설치 안내만 README에 적기. 사용자가 글꼴을 설치해야 하고 채점 환경에서는 통제할 수 없다.

## 한 일
- `fonts/NanumGothic-Regular.ttf`, `fonts/OFL.txt`
- `plotter.setup_korean_font(candidates=None, font_dir=...)`: 시스템 후보가 없으면 `font_dir`의 글꼴을 `font_manager.addfont`로 등록
- README, TEAM_README, ATTRIBUTION 갱신

## 검증
- 테스트 추가: 후보 목록을 없는 이름으로 바꿔 "글꼴 없는 PC"를 흉내 내면 `NanumGothic`이 지정됨 → 44 passed, 6 skipped
- 같은 조건으로 그래프 PNG를 렌더링해 제목·축·범례의 한글이 정상인지 눈으로 확인했다

## 협업 메모
- `plotter.py`만 고쳤고 공유 hotspot 파일 수정 없음

## 포트폴리오 포인트
- 실행 환경에 따라 F10(한글 그래프)이 깨질 수 있는 위험을 **라이선스를 확인한 글꼴 동봉 + 시스템 글꼴 우선 폴백**으로 없앴고, 글꼴 없는 환경을 흉내 낸 테스트로 고정했다.
