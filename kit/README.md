# Agentis — The Kit

씨앗(`seed/agentis.md`)만으로도 에이전트 커널은 동작합니다. **키트**는 더 갖춰진 상태로 시작하게 해주는 템플릿 모음입니다.

v1.9 이후 Agentis는 Cline의 Rules/Workflows 구조를 명확히 나눕니다.

```text
.clinerules/
  agentis.md              # 공통 커널
  10-agent-routing.md     # 자연어 요청 → workflow 라우터
  workflows/              # Cline Workflows 탭용 확정 업무 규칙

agentis/
  memory/                 # 두뇌
  skills/                 # 성장한 스킬
  workflows/              # 내부 초안 + Python 스크립트
  graph/                  # graph/flow/stats 산출물
```

## 쓰는 법

가장 안전한 방법은 레포 루트의 인스톨러입니다.

```bash
python install.py --target "<작업폴더>"
```

수동 설치 시:

1. 이 레포의 `kit/agentis-template/` 폴더를 통째로 복사해서, 작업 폴더에 **`agentis/`** 라는 이름으로 둡니다.
2. `seed/agentis.md` → `.clinerules/agentis.md`
3. `seed/10-agent-routing.md` → `.clinerules/10-agent-routing.md`
4. `kit/agentis-template/workflows/*.workflow.md` → `.clinerules/workflows/*.md`
5. Cline에게 **"안녕"** 이라고 합니다.
6. 에이전트가 인터뷰를 거쳐 `agentis/agent.md` 를 채우고, `agentis/memory/` 의 빈 페이지들을 인터뷰 결과로 채웁니다.

> `kit/agentis-template/` 안의 파일들은 **사용자 작업 폴더로 복사되는 템플릿**입니다. 이 레포 자체에서는 빈 골격 상태입니다.

## 들어있는 것

```text
kit/
  README.md
  agentis-template/
    agent.template.md
    memory/
      README.md
      _index.md  overview.md  log.md  hot.md
      concepts/  entities/  sources/
    skills/
      README.md
      _index.md
    workflows/
      README.md
      00-전체업무순서.workflow.md
      _template.workflow.md
      *.workflow.md
      *.py
    graph/
      README.md
      build_graph.py
      build_flow.py
      agent-stats.py
```

## Workflows 운영 규칙

- `agentis/workflows/` 는 내부 작업장입니다.
- `.clinerules/workflows/` 는 Cline Workflows 탭이 읽는 확정 업무 규칙입니다.
- 새 업무는 먼저 `agentis/workflows/_template.workflow.md` 로 초안을 만들 수 있습니다.
- 반복/확정 업무가 되면 `.clinerules/workflows/<업무>.md` 로 동기화합니다.
- 자연어로 자주 부르는 표현은 `.clinerules/10-agent-routing.md` 에 추가합니다.
- 전체 업무 흐름은 `00-전체업무순서.md` 가 오케스트레이터로 관리하고, 세부 기능 workflow를 참조합니다.

## 정리/검증 워크플로우

업무 완료 후에는 씨드 §3-8 에 따라 정리·검증·기억·보고 마감 루프를 수행합니다.

```bash
python agentis/workflows/프로젝트-정리.py          # 정리 후보 보고서만
python agentis/workflows/프로젝트-정리.py --apply  # 삭제 없이 _archive 로 보관 이동
python agentis/workflows/memory-lint.py            # 두뇌 링크/중복/고아 페이지 점검
python agentis/graph/build_flow.py                 # 주요 업무 flow.html 갱신
python agentis/graph/agent-stats.py                # 능력치 갱신
```

## 그래프 보기

```bash
python agentis/graph/build_graph.py --open
```

`agentis/graph/graph.html` 이 만들어지고 브라우저로 열립니다. 메모리에 페이지가 쌓일수록 그래프가 자랍니다. `flow.html` 은 주요 업무와 workflow 흐름을 보여줍니다.

자세한 구조 설명은 [`docs/cline-rules-workflows-structure.md`](../docs/cline-rules-workflows-structure.md) 를 참고하세요.
