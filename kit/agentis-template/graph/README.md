# graph/ — 두뇌 그래프 + 업무 워크플로우

`graph/` 는 Agentis의 시각화 빌더를 담습니다. 사람에게 먼저 보여주는 파일은 **작업 폴더 루트**에 만들고, 기존 `agentis/graph/` 산출물은 호환용으로 유지합니다.

## 권장 갱신 명령

```bash
python agentis/graph/refresh_views.py --workspace .
```

이 명령이 한 번에 갱신하는 것:

- `<작업폴더>/workflows.html` — `.clinerules/workflows/*.md` 를 결정론적으로 렌더한 사람용 업무 지도
- `<작업폴더>/holonomic-brain.html` — `agentis/memory/`, `skills/`, `workflows/` 를 읽는 사람용 두뇌 지도
- `<작업폴더>/holonomic-brain.json` — 두뇌 지도 데이터
- `agentis/graph/graph.html` + `graph.json` — 기존 3D 두뇌 그래프 호환 뷰
- `agentis/graph/flow.html` — 기존 `agent.md primary_tasks` 스윔레인 호환 뷰
- `agentis/memory/_brain/brain.sqlite` — 검색/회상 인덱스(빌더가 있으면)

## 루트 `workflows.html`

```bash
python agentis/graph/build_workflows.py --workspace .
```

원본은 항상 `.clinerules/workflows/*.md` 입니다. 이 HTML을 직접 편집하지 말고, 확정 업무 markdown을 수정한 뒤 다시 빌드합니다.

결정론 규칙:

- `00-전체업무순서.md` 를 맨 앞에 둡니다.
- 나머지는 파일명 기준 정렬합니다.
- `_template.md`, 숨김 파일, backup 파일은 제외합니다.
- `agentis/workflows/<업무>.py` 가 있으면 실행 스크립트 배지를 표시합니다.

## 루트 `holonomic-brain.html`

```bash
python agentis/graph/build_holonomic_brain.py --root agentis --workspace .
```

`agentis/memory/**/*.md`, `agentis/skills/*/SKILL.md`, `agentis/workflows/*.md` 의 `[[wikilink]]` 관계를 읽어 사람용 두뇌 지도와 건강 상태를 보여줍니다. `agentis/memory/hot.md` 첫 링크는 활성 노드로 표시합니다.

## 기존 호환 뷰

### 3D 두뇌 그래프 (`agentis/graph/graph.html`)

```bash
python agentis/graph/build_graph.py
python agentis/graph/build_graph.py --open
```

만들어지는 것:

- `graph.json` — 노드(페이지)·엣지(`[[링크]]`)·통계. 결정론적(같은 memory → 같은 json).
- `graph.html` — Three.js + 3d-force-graph 인라인 자체완결 3D 뷰.

### 주요 업무 스윔레인 (`agentis/graph/flow.html`)

```bash
python agentis/graph/build_flow.py
python agentis/graph/build_flow.py --open
```

`flow.html` 은 “지난 업무 히스토리”가 아니라 `agent.md` 의 `primary_tasks` 3~5개와 각 업무의 표준 처리 단계를 보여주는 운영 지도입니다. `memory/log.md` 는 처리 횟수/최근 처리일/토큰 평균 통계에만 사용합니다.

## 언제 갱신하나

- `.clinerules/workflows/` 가 바뀔 때: `refresh_views.py` 실행 → 루트 `workflows.html` 갱신
- `memory/`, `skills/`, `workflows/`, `hot.md` 가 바뀔 때: `refresh_views.py` 실행 → 루트 `holonomic-brain.html` 및 기존 graph 갱신
- `agent.md primary_tasks` 나 `memory/log.md` 가 바뀔 때: `refresh_views.py` 실행 → 기존 `flow.html` 갱신
- 업무 완료 루프 마지막에는 가능하면 `refresh_views.py` 와 `agent-stats.py` 를 함께 실행하고 실패 여부를 보고합니다.

## 업그레이드 안전장치

생성물(`workflows.html`, `holonomic-brain.html`, `graph.html`, `flow.html`, `graph.json`)은 프로젝트에서 자란 산출물이므로 표준 키트 업그레이드 시 덮어쓰지 않습니다. 새 버전의 kit-owned 스크립트(`build_workflows.py`, `build_holonomic_brain.py`, `refresh_views.py`, `build_graph.py`, `build_flow.py`)만 백업 후 갱신하고, 사용자가 다시 빌드할 때 새 형식이 반영됩니다.
