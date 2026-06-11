# Agentis · Cline Rules / Workflows 구조

Agentis는 Cline의 **Rules**와 **Workflows**를 분리해서 사용한다. 핵심은 “항상 적용되는 커널은 Rules에, 반복·확정 업무 절차는 Workflows에, 자연어 요청 라우팅은 얇은 Rule에” 두는 것이다.

## 결론 구조

```text
프로젝트/
├─ .clinerules/
│  ├─ agentis.md                 # 공통 커널: 정체성, 기억, 검증, 완료 루프
│  ├─ 10-agent-routing.md        # 자연어 요청 → workflow 라우팅 규칙
│  └─ workflows/                 # Cline Workflows 탭이 읽는 업무별 규칙
│     ├─ 00-전체업무순서.md       # 오케스트레이터
│     ├─ <업무A>.md
│     ├─ <업무B>.md
│     └─ _template.md
│
└─ agentis/                      # 에이전트 내부 두뇌와 작업장
   ├─ agent.md
   ├─ memory/
   ├─ skills/
   ├─ workflows/                 # 스크립트·초안·진화 후보
   └─ graph/
```

## 역할 분리

### 1. `.clinerules/agentis.md` — 커널

항상 적용되어야 하는 공통 운영 원칙을 둔다.

- 첫 부팅 / 평소 세션 판정
- 주요 업무 분류
- 삭제 금지 / 보관 원칙
- 검증 우선
- 기억 갱신
- graph / flow / stats 갱신
- Git 상태 확인
- 완료 보고 형식

여기에 모든 업무별 세부 절차를 넣지 않는다. 커널이 너무 커지면 Cline이 실제 업무 흐름을 놓치기 쉽다.

### 2. `.clinerules/10-agent-routing.md` — 라우터

사용자가 slash command 없이 자연어로 요청해도 적절한 workflow를 찾게 하는 얇은 룰이다.

예:

```md
사용자가 “오늘 업무 진행해”라고 말하면
`.clinerules/workflows/00-전체업무순서.md` 절차를 우선 따른다.

사용자가 “브랜치 만들어줘”라고 말하면
`.clinerules/workflows/브랜치-내보내기.md` 절차를 따른다.
```

Cline의 workflow 공식 호출은 slash 기반일 수 있으므로, 자연어 자동 호출은 “라우팅 룰이 workflow 참조를 강하게 유도하는 방식”으로 설계한다.

### 3. `.clinerules/workflows/` — 확정 업무 규칙

Cline 하단 **Workflows** 탭이 읽는 프로젝트 로컬 workflow 위치다. 확정 업무, 반복 업무, 주요 업무는 여기에 둔다.

원칙:

- `00-전체업무순서.md` 는 오케스트레이터다.
- 기능별 workflow는 독립 실행 가능해야 한다.
- 전체업무순서는 기능별 workflow를 참조만 하고 세부 로직을 다 품지 않는다.
- 같은 이름의 전역 workflow가 있어도 프로젝트 로컬 workflow가 우선한다는 가정으로 관리한다.

### 4. `agentis/workflows/` — 내부 작업장

에이전트가 성장하면서 만드는 스크립트, workflow 초안, 결정론 처리기를 둔다.

- `*.workflow.md`: 내부 초안·원본
- `*.py`: 실제 처리 스크립트
- 반복/확정된 절차: `.clinerules/workflows/<업무>.md` 로 승격/동기화

즉, `agentis/workflows/` 만 갱신하고 `.clinerules/workflows/` 를 갱신하지 않으면 Cline Workflows 탭에서 누락될 수 있다.

## 새 workflow 추가 규칙

1. `agentis/workflows/_template.workflow.md` 로 초안 작성
2. 가능하면 `agentis/workflows/<업무>.py` 로 결정론 처리 구현
3. 사용자와 절차가 확정되면 `.clinerules/workflows/<업무>.md` 로 복사
4. 자연어로 자주 부르는 표현은 `.clinerules/10-agent-routing.md` 에 추가
5. 완료 시 `agentis/memory/log.md`, `hot.md`, `graph/flow/stats` 갱신

## 설치 시 배포되는 것

`install.py` 는 다음을 설치한다.

1. `.clinerules/agentis.md`
2. `.clinerules/10-agent-routing.md`
3. `.clinerules/workflows/*.md`
4. `agentis/` 키트

이미 사용자가 수정한 routing/workflow 룰은 기본적으로 보존하고, `--force` 일 때만 백업 후 갱신한다.

## 설계 판단

이 구조가 좋은 이유:

- 커널이 비대해지지 않는다.
- Cline Workflows 탭의 프로젝트 로컬 workflow 기능을 활용한다.
- 자연어 요청도 라우터를 통해 workflow로 연결된다.
- 전체 업무와 기능별 업무가 분리되어 재사용성이 높다.
- `agentis/` 내부 진화와 `.clinerules/` 배포 규칙이 구분된다.
