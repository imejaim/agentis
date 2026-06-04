# graph/ — 두뇌 그래프 + 업무 워크플로우

`graph/` 는 두 가지 시각화를 담당합니다.

1. `graph.html` — `memory/` 의 마크다운 위키를 노드/엣지 그래프로 만든 **두뇌 그래프**
2. `flow.html` — `agent.md` 의 `primary_tasks` 를 기반으로 만든 **주요 업무별 워크플로우 다이어그램**

둘 다 자체완결 HTML 이며, 사내망/오프라인에서도 열립니다.

## 두뇌 그래프 빌드

```bash
python agentis/graph/build_graph.py            # graph.json + graph.html 생성
python agentis/graph/build_graph.py --open     # 생성 후 브라우저로 graph.html 열기
python agentis/graph/build_graph.py --memory <경로> --out <경로>
```

만들어지는 것:
- `graph.json` — 노드(페이지)·엣지(`[[링크]]`)·통계. 결정론적(같은 memory → 같은 json).
- `graph.html` — 자체완결형. D3·CDN 등 외부 의존 없음. 드래그=이동, 휠=확대, 노드 드래그=고정, 노드 클릭=이웃 강조.

## 업무 워크플로우 빌드 (`flow.html`)

```bash
python agentis/graph/build_flow.py
python agentis/graph/build_flow.py --open
```

### v1.9 규칙

`flow.html` 은 “지난 업무 히스토리”를 시간순으로 늘어놓는 파일이 아닙니다.
해당 프로젝트의 **주요 업무 3~5개**를 왼쪽 스윔레인으로 두고, 각 업무의 표준 처리 단계를 다이어그램으로 보여주는 운영 지도입니다.

예를 들어 프로젝트의 주요 업무가 3개라면:
- p1: 고객 문의 처리
- p2: 월간 리포트 작성
- p3: 장애 대응

`flow.html` 은 위 3개의 레인과 각 레인의 처리 단계(`접수 → 확인 → 처리 → 보고`)를 보여줘야 합니다. `memory/log.md` 는 각 레인의 “처리 횟수/최근 처리일/토큰 평균” 같은 통계에만 사용합니다.

### `agent.md` 작성 예시

```yaml
primary_tasks:
  - id: 1
    name: 고객 문의 처리
    description: 문의 접수부터 답변/기록까지
    success_metric: 답변 누락 0, SLA 초과 0
    workflow:
      - 문의 접수
      - 원인/자료 확인
      - 답변 작성
      - 결과 기록
  - id: 2
    name: 월간 리포트 작성
    description: 월간 지표를 수집·검증해 보고서 발행
    success_metric: 매월 지정일 전 발행
    workflow:
      - 데이터 수집
      - 수치 검증
      - 보고서 작성
      - 승인/발행
  - id: 3
    name: 장애 대응
    description: 장애 감지부터 복구 회고까지
    workflow:
      - 알림 확인
      - 영향 범위 파악
      - 복구 조치
      - 사후 기록
```

`workflow:` 가 없으면 기본 3단계(`요청/트리거 확인 → 처리/검증 → 산출물 보고/기억 갱신`)가 자동으로 들어갑니다.

## 언제 갱신하나

- `memory/` 가 바뀔 때: `build_graph.py`, `agent-stats.py` 갱신
- `agent.md` 의 `primary_tasks` 나 주요 업무 정의가 바뀔 때: `build_flow.py` 갱신
- 업무 완료 루프 마지막에는 가능하면 `graph.html`, `flow.html`, `stats.md` 를 함께 갱신하고 실패 여부를 보고합니다.

## 업그레이드 안전장치

`graph.html`, `flow.html`, `graph.json` 은 각 프로젝트에서 생성·성장한 산출물입니다. 표준 키트 업그레이드 시 **덮어쓰지 않습니다.**
새 버전의 `build_graph.py`/`build_flow.py` 같은 kit-owned 스크립트는 백업 후 갱신하고, 기존 생성물은 그대로 둔 뒤 사용자가 다시 빌드할 때 새 형식이 반영됩니다.
