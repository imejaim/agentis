# Agentis 업무 라우팅 규칙

이 파일은 Cline Rules에 들어가는 **라우터**입니다. 공통 운영 커널은 `.clinerules/agentis.md` 에 있고, 실제 반복/확정 업무 절차는 `.clinerules/workflows/` 아래의 workflow 파일을 따른다.

## 기본 원칙

1. 사용자가 자연어로 업무를 요청하면 먼저 요청을 한 줄로 분류한다.
2. `.clinerules/workflows/` 에 해당 업무 또는 가장 가까운 workflow가 있으면 그 파일을 우선 읽고 따른다.
3. 여러 workflow가 관련되면 `.clinerules/workflows/00-전체업무순서.md` 를 오케스트레이터로 사용하고, 기능별 workflow를 순서대로 참조한다.
4. slash 호출이 가능하면 사용자가 직접 `/<workflow명>` 으로 부를 수 있지만, 사용자가 자연어로 말해도 라우팅 규칙에 따라 적절한 workflow를 찾아 실행한다.
5. `.clinerules/workflows/` 에 없는 반복 업무가 확정되면 업무 종료 전 새 workflow 초안을 만들고 사용자 확인 후 저장한다.

## 자연어 라우팅

- "오늘 업무 진행해", "오늘 것 처리해", "일일 업무 해줘", "정해진 순서대로 해줘"
  - `.clinerules/workflows/00-전체업무순서.md` 를 우선 따른다.

- "문서 파싱", "자료 읽고 정리", "파일에서 정보 뽑아줘"
  - 문서/자료 처리 workflow가 있으면 따른다.
  - 없으면 `.clinerules/workflows/_template.md` 형식으로 새 workflow 후보를 만든다.

- "검증해줘", "결과 확인해줘", "업무 결과 체크"
  - 검증 workflow 또는 `.clinerules/agentis.md` 의 완료 체크리스트를 따른다.

- "브랜치 만들어줘", "분신 만들어줘", "내보내기"
  - `.clinerules/workflows/브랜치-내보내기.md` 를 따른다.

- "팩 병합", "받은 에이전트 역량 합쳐줘"
  - `.clinerules/workflows/팩-병합.md` 를 따른다.

- "씨드 업그레이드", "Agentis 룰 업데이트"
  - `.clinerules/workflows/씨드-업그레이드.md` 를 따른다.

## 실행 보고

업무 시작 보고에는 다음을 짧게 포함한다.

- 분류: 주요 업무 / 부수 업무 / 새 workflow 후보
- 사용할 workflow: `.clinerules/workflows/<파일>.md`
- 산출물 위치
- 검증 방법

업무 완료 보고는 `.clinerules/agentis.md` 의 완료 체크리스트를 따른다.
