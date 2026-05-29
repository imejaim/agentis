# 로그

새 항목은 맨 위에. 형식 (v1.6 컨벤션):
- 주요 업무: `## [YYYY-MM-DD] task [primary:N] | <제목>` (N = `agent.md` 의 `primary_tasks` 인덱스)
- 부수 업무: `## [YYYY-MM-DD] task [aux] | <제목>`
- 그 외 type (setup|ingest|skill|lint|note|seed) 은 자동으로 [aux] 취급

---

## [2026-05-22] task [primary:4] | 모델Y 제출 패키지 최종 점검 리포트 생성
- [[skills/checklist-대조]] + 시험성적서 표를 묶어 한 페이지 리포트. 홍길동 검토 5분 → ok. tokens: 4200, sec: 12.

## [2026-05-20] task [primary:1] | 모델Y 체크리스트 대조 v3
- 14개 항목 중 2개 누락 적발 → 홍길동 보고. tokens: 1800, sec: 4.

## [2026-05-18] task [aux] | 사용자 환경 설정 — VS Code 한글 폰트
- 홍길동 요청 (부수). settings.json 안내. tokens: 800.

## [2026-05-15] task [primary:2] | 모델Y 시험성적서 항목 추출
- [[sources/2026-05-15-시험성적서-모델Y]] 에서 15개 항목 추출. 카운트 15==15. tokens: 2100, sec: 6.

## [2026-05-14] task [primary:3] | 모델Y 추출표 대조 검증 보고
- 항목 15건 1:1 대조. 1건 ?? 마킹 (스캔 흐림). tokens: 1500, sec: 5.

## [2026-05-12] note | 제출 패키지 "최종 점검 리포트" 요청
- 홍길동 요청: 체크리스트 대조 + 시험성적서 표를 한 장으로 묶은 리포트. [[hot]] 에 다음 할 일로 적음. → primary_tasks 4번으로 승격.

## [2026-05-10] ingest | 인증기관 제출문서 목록 v2
- [[sources/2026-05-10-제출문서목록-v2]] 요약. [[entities/kc-안전인증]] 의 요구 문서 목록 갱신. [[concepts/체크리스트-대조-원칙]] 에 "버전 바뀌면 diff부터" 규칙 추가.

## [2026-05-09] skill | checklist-대조 추가
- 체크리스트 대조가 제출 건마다 반복 → [[skills/checklist-대조]] 스킬로 승격 (SKILL.md + run.py). [[concepts/체크리스트-대조-원칙]] 을 코드로 옮김(정규화·동의어·개수검증).

## [2026-05-08] task [primary:2] | 모델X 시험성적서 항목 추출
- [[sources/2026-05-08-시험성적서-모델X]] 에서 12개 항목 추출 → 표. 카운트 검증 통과(12==12). 스캔 1페이지 OCR 흐릿 → 2개 칸 `??` 표시하고 홍길동 확인 요청. [[concepts/시험성적서-항목-스키마]] 초안 작성. tokens: 2400, sec: 8.

## [2026-05-07] setup | 규격이 부팅
- 이름·목적·범위 인터뷰 완료. `agentis/` 구조 생성. [[entities/홍길동-품질팀]], [[concepts/kc-rohs-기초]] 초안 작성.
