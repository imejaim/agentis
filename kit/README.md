# Agentis — The Kit

씨앗(`seed/agentis.md`)만으로도 에이전트는 동작합니다. **키트**는 "더 갖춰진 상태로 시작"하게 해주는 템플릿 모음입니다.

## 쓰는 법

1. 이 레포의 `kit/agentis-template/` 폴더를 통째로 복사해서, 작업 폴더에 **`agentis/`** 라는 이름으로 둡니다.
2. `seed/agentis.md` 내용을 작업 폴더의 `.clinerules` (또는 `.clinerules/agentis.md`) 로 넣습니다.
3. Cline에게 **"이 폴더(`agentis/`) 보고 셋업해줘"** 또는 그냥 **"안녕"** 이라고 합니다.
4. 에이전트가 인터뷰를 거쳐 `agentis/agent.md` 를 채우고(템플릿: `agent.template.md`), `agentis/memory/` 의 빈 페이지들을 인터뷰 결과로 채웁니다.

> `kit/agentis-template/` 안의 파일들은 **사용자 작업 폴더로 복사되는 템플릿**입니다. 이 레포 자체에서는 빈 골격 상태입니다.

## 들어있는 것

```
kit/
  README.md                       ← 이 파일
  agentis-template/                ← 복사해서 작업폴더의 agentis/ 로
    agent.template.md              ← 정체성 템플릿 (인터뷰 결과로 채워 agent.md 로 저장)
    memory/                        ← "두뇌" — 살아있는 LLM-위키
      README.md                    ← 메모리 운영 규약 (페이지 포맷, [[링크]], 언제 갱신)
      _index.md  overview.md  log.md  hot.md
      concepts/  entities/  sources/
    skills/
      README.md                    ← 스킬 포맷 (SKILL.md + run.py)
      _index.md
    workflows/
      README.md                    ← 워크플로우 포맷
      _template.workflow.md         ← 새 워크플로우 만들 때 복사
    graph/
      README.md
      build_graph.py                ← memory/ → graph.json + graph.html (표준 라이브러리만, 외부 의존 0)
```

## 그래프 보기

```bash
python agentis/graph/build_graph.py --open
```
`agentis/graph/graph.html` 이 만들어지고 브라우저로 열립니다. 메모리에 페이지가 쌓일수록 그래프가 자랍니다. (의존성 없음 — 사내망/오프라인에서도 됩니다. `graphify` 가 설치돼 있으면 에이전트가 의미관계까지 더 풍부하게 그릴 수도 있습니다.)
