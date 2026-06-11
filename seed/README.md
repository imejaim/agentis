# Agentis — The Seed

**`agentis.md` 는 에이전트 커널입니다.** 별도 서버 인프라는 필요 없습니다. 다만 Cline의 Rules/Workflows 구조를 제대로 쓰려면 커널 하나만 두는 방식보다 **Rules + Routing + Workflows** 구조를 권장합니다.

씨앗 커널은 **`agentis.md`** 입니다. 이걸 Cline(또는 cline SR) 워크스페이스 룰로 넣고 "안녕"이라고 하면, 에이전트가 인터뷰를 거쳐 자기 정체성과 "두뇌"(`agentis/`)를 스스로 만듭니다.

## 권장 설치 구조

```text
.clinerules/
  agentis.md              # 공통 커널: 기억, 검증, 완료 루프
  10-agent-routing.md     # 자연어 요청 → workflow 라우터
  workflows/              # Cline Workflows 탭용 업무별 규칙
    00-전체업무순서.md
    <업무>.md
```

가장 안전한 설치 방법은 레포 루트의 결정론 인스톨러입니다.

```bash
python install.py --target "<작업폴더>"
```

수동 설치 시:

1. `seed/agentis.md` → `.clinerules/agentis.md`
2. `seed/10-agent-routing.md` → `.clinerules/10-agent-routing.md`
3. `kit/agentis-template/workflows/*.workflow.md` → `.clinerules/workflows/*.md`
4. 선택: `kit/agentis-template/` → `agentis/`

> 단일 `.clinerules` 파일에 `agentis.md` 만 넣어도 기본 커널은 동작하지만, 확정 업무 흐름을 Cline Workflows 탭에 태우려면 위 디렉토리 구조를 권장합니다.

## 시작

Cline 대화창에 **`안녕`** 이라고 입력하세요. 에이전트가:

1. 이름을 지어달라고 합니다.
2. 무슨 업무를 도울지 짧게 인터뷰합니다. 한 번에 한 질문만 합니다.
3. 설계 요약을 보여주고 승인받으면 `agentis/` 구조를 만듭니다.
4. 사용법을 안내하고 첫 업무를 묻습니다.

이후 세션이 바뀌어도 `agentis/` 의 기억을 읽고 이어서 진행합니다. `agentis/graph/graph.html` 또는 `agentis/graph/flow.html` 을 브라우저로 열면 지식과 업무 흐름이 쌓이는 모습이 보입니다.

## 만들어지는 것

에이전트 내부 두뇌와 작업장:

```text
agentis/
  agent.md          # 에이전트 정체성
  memory/           # 세션 간 기억의 전부
    _index.md  overview.md  log.md  hot.md
    concepts/  entities/  sources/
  skills/           # 에이전트가 키워가는 스킬
  workflows/        # 내부 workflow 초안 + Python 스크립트
  graph/            # graph.html / flow.html / stats.md
```

Cline이 직접 읽는 룰 영역:

```text
.clinerules/
  agentis.md
  10-agent-routing.md
  workflows/
```

> `agentis/workflows/` 는 에이전트 내부 작업장입니다. 반복/확정된 업무 절차는 `.clinerules/workflows/` 로도 동기화해야 Cline Workflows 탭에서 누락되지 않습니다.

## 더 풍부하게

`kit/` 폴더에는 workflow 템플릿, 스킬 라이브러리, 메모리 스캐폴드, 그래프 뷰어가 들어 있습니다. `kit/agentis-template/` 를 작업 폴더에 `agentis/` 로 복사하면 더 갖춰진 상태로 시작합니다.

확정된 workflow는 다음 흐름으로 관리합니다.

1. `agentis/workflows/_template.workflow.md` 로 초안 작성
2. 필요하면 `agentis/workflows/<업무>.py` 로 결정론 처리 구현
3. 사용자와 절차가 확정되면 `.clinerules/workflows/<업무>.md` 로 동기화
4. 자연어 호출 표현은 `.clinerules/10-agent-routing.md` 에 추가

---

더 자세한 셋업 방법, 에이전트 공유(브랜치), 사내 깃 배포는 레포 루트 [`README.md`](../README.md) 와 [`docs/cline-rules-workflows-structure.md`](../docs/cline-rules-workflows-structure.md) 참고.
