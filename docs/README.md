# docs

과제 제출 이후 고도화 단계의 진행 기록이다. 포트폴리오 작성용 재료를 모아 둔다.

| 폴더/파일 | 내용 |
|---|---|
| [collaboration.md](collaboration.md) | 협업 규칙: 작업 사이클, 충돌 예방, 충돌 해결 절차, 사용 스킬 |
| [devlog/](devlog/) | 작업(PR)마다 한 파일. 문제 → 판단 → 한 일 → 검증 → 포트폴리오 포인트 |
| [decisions/](decisions/) | 설계 결정 기록(ADR). 왜 그렇게 했는지 |
| [presentation.md](presentation.md) | 발표 구성안(10분), 데이터 특이 사항 근거, 예상 질문과 답 |
| [desk-demo.md](desk-demo.md) | 자리 설명용 대본(3분): 대시보드 하나로 설명하는 순서와 한 줄 답 |

## 작업 기록 목록

| 날짜 | 작업 | 파일 |
|---|---|---|
| 2026-11-23 | 협업 환경 구성 (충돌 점검 스크립트, 규칙, 스킬) | [devlog/2026-11-23-collab-setup.md](devlog/2026-11-23-collab-setup.md) |
| 2026-11-23 | O2 불량 급증 자동 탐지 | [devlog/2026-11-23-spike-detection.md](devlog/2026-11-23-spike-detection.md) |
| 2026-11-24 | 한글 글꼴 동봉 | [devlog/2026-11-24-bundled-font.md](devlog/2026-11-24-bundled-font.md) |
| 2026-11-24 | D99 제외 불량률 옵션 | [devlog/2026-11-24-d99-option.md](devlog/2026-11-24-d99-option.md) |
| 2026-11-24 | O1 불량 박스 분석 | [devlog/2026-11-24-box-analysis.md](devlog/2026-11-24-box-analysis.md) |
| 2026-11-24 | 제출 전 점검 도구, 견고성 보강 | [devlog/2026-11-24-final-check.md](devlog/2026-11-24-final-check.md) |
| 2026-11-24 | 제공 데이터 최종 점검 결과 (O1·O2 실제 수치) | [devlog/2026-11-24-real-data-results.md](devlog/2026-11-24-real-data-results.md) |
| 2026-11-24 | AI_USAGE PR #1~#4 직접 확인 내용 기록 (jayhuni) | [devlog/2026-11-24-ai-usage-pr1-4.md](devlog/2026-11-24-ai-usage-pr1-4.md) |

## 설계 결정 목록

| 번호 | 제목 |
|---|---|
| [ADR-001](decisions/ADR-001-feature-modules.md) | 새 분석 기능은 별도 모듈에 둔다 |
| [ADR-002](decisions/ADR-002-spike-criterion.md) | 불량 급증 판단 기준 |

## 포트폴리오로 옮길 때
`devlog/` 각 파일의 "포트폴리오 포인트"와 "검증" 수치를 모아 루트의 [PORTFOLIO.md](../PORTFOLIO.md)에 "고도화" 절로 추가한다. 기간별 커밋 요약은 `what-did-i-get-done` 스킬로 뽑을 수 있다.
