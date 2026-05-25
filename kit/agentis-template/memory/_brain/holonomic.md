# 홀로노믹 브레인 — Agentis 식 적용 (컨셉 노트)

> **상태**: 컨셉 노트. v1.5 시점에 Agentis 와 `imejaim/OffSpace-Self-Growth-Agent/holonomic-brain-kit/` 를 비교·매핑한 결과를 박아둔 것. 이 노트가 곧 두뇌의 *원리표* — 페이지가 어떻게 분산·자기유사적으로 자라는지 설명한다.

원천 레퍼런스:
- `reference/OffSpace-Self-Growth-Agent/holonomic-brain-kit/` (Ko-bujang / Oh-gwajang / Jem-daeri 캐릭터 SVG + SCHEMA.md + operating-model.md + project-memory.json 템플릿).
- 보편 원리: Pribram 의 holonomic brain theory (분산·간섭 패턴으로 기억이 저장됨), Bohm 의 implicate order (각 부분에 전체가 접혀 있음).

---

## 1) 한 페이지 = 두뇌의 한 조각, 동시에 두뇌 전체의 축약

홀로노믹 두뇌의 핵심 원리는 **분산 저장**이다. 하나의 기억이 한 자리에만 박히는 게 아니라, 여러 페이지에 부분씩 흩어져 있고 — 그 페이지들의 *상호 참조*가 곧 기억의 본체다.

Agentis 에선:

| 홀로노믹 개념 | Agentis 의 표현 |
|---|---|
| 분산 저장 | `concepts/` `entities/` `sources/` 가 한 사실을 여러 시점에서 가짐 |
| 간섭 패턴 = 기억 | `[[..]]` 위키링크가 만드는 그래프 (= `brain.sqlite` 의 `links` 테이블) |
| implicate order (접힌 질서) | `_index.md` + `overview.md` — 각 페이지에서 펼쳐지는 전체의 축약본 |
| 회상 (hologram readout) | `query_brain.py` 의 hybrid 검색 — 키워드/시맨틱 시드 + 그래프 1-hop |

페이지 한 장만 봐도 그 페이지의 frontmatter(tags, created, updated) + H1 제목 + [[..]] 링크들로 두뇌 전체 구조의 *작은 사본*이 박혀 있다. 이게 OffSpace 의 *"the brain must graph itself from the project's own evidence"* 와 같은 결.

---

## 2) 자기성장 루프 — Hermes 식 자가진화 와의 매핑

`holonomic-brain-operating-model.md` 의 "Shared Brain Rules" 는 다음을 요구한다:

- durable findings → wiki 에 쓰기
- 운영 규칙 바뀌면 `.omc/project-memory.json` 갱신
- 한 에이전트의 채팅 컨텍스트를 사적 진실로 두지 말기
- 임시 대화보다 공유 산출물 우선

Agentis 씨드(`seed/agentis.md`)의 §3 작업 루프 + §3-5 자가 스킬 추가 + §3-7 자가 도태가 정확히 이걸 코드화한 것:

| 홀로노믹 룰 | Agentis 씨드 조항 |
|---|---|
| durable findings → wiki | §3-2 새 개념/엔티티/소스 페이지 생성 + `_index`·`log` 갱신 |
| 운영 규칙 바뀌면 메모리 갱신 | §3-3 `overview.md` / `hot.md` 정비 |
| 임시 대화 ≠ 진실 | §3-4 모든 작업은 `log.md` 한 줄로 결정론 기록 |
| 자가성장 | §3-5 반복 패턴 → `skills/<이름>/` 승격 |
| 자가 도태 (Agentis 가 추가) | §3-7 → 본 키트의 `workflows/skill-도태.py` |

즉 **홀로노믹 브레인은 *원리*, Agentis 씨드는 *실행 규약*, kit 의 .py 는 *결정론 실행체*** 라는 3층 구조.

---

## 3) 메모리 layer — OffSpace 4층 ↔ Agentis 5층의 대응

OffSpace 의 4층 레이어:
1. **Raw** — `docs/raw/` (불변 원천)
2. **Wiki** — `docs/wiki/` (큐레이션 마크다운)
3. **Schema** — `docs/wiki/SCHEMA.md` + `CLAUDE.md`
4. **Operational memory** — `.omc/project-memory.json`

Agentis 의 5층:

| OffSpace | Agentis |
|---|---|
| Raw | (사용자의 원본 자료 — `agentis/` 바깥. 절대 수정 X) |
| Wiki | `agentis/memory/{concepts,entities,sources,_index,overview,log,hot}` |
| Schema | `.clinerules/agentis.md` (씨드) + `kit/agentis-template/memory/README.md` |
| Operational memory | `agentis/memory/stats.md` (능력치) + `agentis/graph/graph.json` |
| **+ Brain Index (v1.5 신규)** | `agentis/memory/_brain/brain.sqlite` — *검색·회상* 계층 |

Brain Index 는 OffSpace 4층에 *없던* 새 층이다. 이유:
- OffSpace 는 채팅 + git 검색에 의지 → 사내 cline SR + 사내망 제약 환경에선 검색이 그만큼 빠르지 않음.
- Agentis 의 결정론 우선 원칙 → 검색도 결정론·재실행 가능해야 함 → SQLite + 임베딩 캐시.

---

## 4) 캐릭터 = 공유 정체성 (Ko-bujang / Oh-gwajang / Jem-daeri)

OffSpace 키트의 핵심 자산은 *세 캐릭터 SVG*다. 이미 v1.4 에서 Agentis 가 `kit/agentis-template/graph/assets/characters/` 로 동봉했다 (Ko-bujang.svg / Oh-gwajang.svg / Jem-daeri.svg). v1.4.1 에서 그래프 안 빌보드 sprite 로 들어갈 예정.

홀로노믹 관점에서 캐릭터의 의미: 여러 에이전트(=여러 도구·세션)가 같은 페르소나를 공유하면, **사용자 머릿속에선 그게 한 사람으로 통합**된다. 즉 캐릭터는 *분산 시스템의 사용자 측 정합성 장치*다. cline SR 세션이 바뀌어도 "이 곰이 그 곰" 이라는 정체성이 유지되면 사용자에겐 같은 두뇌가 계속되는 느낌.

---

## 5) Brain Index 가 풀어주는 문제 — 한 페이지 요약

```
질문: "규격 인증 절차"
        │
        ▼  query_brain.py
        │
   ┌────┴────┐
keyword     semantic           ← 두 다른 *간섭 패턴*
(FTS5 BM25) (sentence-transformers, 가용 시)
   │            │
   └─── RRF ────┘              ← 결합 (Reciprocal Rank Fusion)
        │
        ▼
   graph 1-hop                 ← 시드의 이웃 = 그 기억의 주변 회상
        │
        ▼
   {results: [...], notes: [...]}
```

- **keyword** = "표면 일치" — 단어가 그 자리에 있는지.
- **semantic** = "의미 일치" — 다른 단어로 쓰여도 같은 뜻이면 잡힘.
- **RRF 결합** = 두 모달의 잘하는 영역이 다르므로 서로 보강.
- **graph 1-hop** = 시드 페이지의 이웃 = "이 기억과 함께 묶여 있는 것들" — 홀로노믹의 *간섭 패턴*에 해당.

---

## 6) 위반하면 안 되는 것 (홀로노믹 폴리시)

- **다른 프로젝트의 메모리·인시던트·위키 페이지를 새 프로젝트에 그대로 복사하지 말 것.** OffSpace 룰 그대로 가져옴. 두뇌는 자기 증거에서 자라야 함.
- **자동 ingest 의 스텁(`auto-stub` 태그)을 그대로 두지 말 것.** 사용자가 읽고 채워야 그 페이지가 진짜 기억이 됨. 안 채워진 스텁이 30일 지나면 `memory-lint.py` 가 잡아냄.
- **`_brain/` 자체를 인덱스 대상에 넣지 말 것.** 자기 자신을 회상하는 무한루프가 됨 (build_brain_index.py 에 가드 박혀 있음).

---

## 7) 다음 단계 후보 (v1.6+)

- **간섭 패턴 시각화** — graph.html 에 "두 페이지의 공통 이웃 개수" 를 엣지 두께로. (Pribram 의 holographic memory 시각화의 결정론 근사.)
- **Self-referential pages** — `_index.md` 가 자기 자신의 요약을 보유 (implicate order 의 *접힌* 부분).
- **다중 에이전트 동시 작업 충돌 방지** — OffSpace 의 active-tasks.md 패턴 (홀로노믹 §"Concurrency & WIP Synchronization Protocol") 을 Agentis 의 `memory/hot.md` 와 매핑.

---

*— v1.5. 사용자의 `imejaim/OffSpace-Self-Growth-Agent/holonomic-brain-kit/` 가 사내 클론으로 들어와 있으면 위 매핑이 그대로 동작. 사내망 클론 실패 시엔 보편 holonomic 원리만으로도 충분 — Brain Index 와 그래프 1-hop 이 핵심.*
