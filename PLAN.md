# Agentis — 기획서 (v0.4)

> 작성: 코부장 / 2026-05-13. 대표님 3차 피드백 반영(public 전환, v1.0 범위 확정, 그래프 레퍼런스 확정).
> 진행 중 문서 — "조금씩 더 살펴보면서 추가하고 다듬자" 기조. 끝의 §10(대표님 확인) 봐주세요.
> 코드 레퍼런스: `reference/` 폴더에 원본 레포 클론됨(깃이그노어). 그래프 스타일 레퍼런스: `docs/ref-graph-style.png`.

---

## 0. 한 줄 요약

**Agentis** — 사내 **VS Code + cline SR** 환경에서, **Cline 룰(md 파일) 기반**으로 돌아가는 **업무처리 에이전트 키트**.
사용자가 에이전트 이름을 짓고 목적을 정하면(clarify 인터뷰) → 일하면서 **Cline 메모리뱅크가 살아있는 LLM-위키처럼 스스로 확장**되고("두뇌") → **Obsidian처럼 graphify로 그래프화되어 지식이 쌓이는 게 눈에 보이고** → 에이전트가 **스스로 스킬/지식을 추가하며 진화** → **사용자도 "에이전틱 업무처리"를 체득하며 함께 성장**.
GitHub `imejaim/agentis` (**public**). 모토: **카오스 → 유니버스.**

---

## 1. 목적과 성격 (확정)

- ❌ 코딩 에이전트 / ❌ 개인 비서 → ✅ **업무처리 에이전트** (사내 업무를 에이전틱하게 처리)
- ✅ **공개 배포** — `github.com/imejaim/agentis` (public). 회사·동료 누구나 클론/다운로드.
- ✅ **진입점 = Cline 룰(markdown 파일들)** — superpowers가 스킬을 md로 구성한 것처럼, Agentis는 룰/메모리/스킬을 전부 md 파일로.
- ✅ **교육 목적 겸함** — 동료들이 "에이전틱 업무처리란 이런 거구나"를 직접 경험.
- ✅ **공진화** — 매 상호작용이 (a) 사용자의 에이전틱 역량 (b) 에이전트의 지식·스킬, 둘 다를 키운다.
- ✅ **셋팅 최소화** — ① 폴더 복붙 → "클라인아 이거 보고 셋팅해줘" ② 또는 룰 파일 1개 + "안녕".
- ✅ **단순하게** — 사내 프록시/인증서/내부망 제약 → 빌드·설치 의존 최소화. 필요하면 cline SR에게 설치 위임.

---

## 2. v1.0 범위 (확정) ⭐

v1.0 = "표준 Cline 위에서, md 파일만으로, 다음 3개가 맞물려 도는 것":

### (1) Cline 룰 기반 골격 — "superpowers처럼"
- 모든 동작을 **markdown 파일**로 정의: 부트스트랩 룰, clarify 인터뷰 스크립트, 워크플로우, 스킬.
- `reference/superpowers/skills/`·`docs/`의 "md = 강제 워크플로우" 구조를 참고해 업무 에이전트용으로 각색.
- 진입: Cline 워크스페이스 룰(`.clinerules`)이 부트스트랩 md를 가리킴 → "안녕"하면 흐름 시작.

### (2) 살아있는 메모리 = Cline 메모리뱅크 + Hermes 자가확장 + LLM-위키 — "두뇌"
- Cline은 원래 **메모리뱅크**(`memory-bank/` 안 `projectbrief.md`·`productContext.md`·`activeContext.md`·`systemPatterns.md`·`techContext.md`·`progress.md` 등)를 세션 시작마다 읽고 갱신함.
- 이걸 그대로 쓰지 않고 **진화시킴**:
  - **Hermes처럼 자가확장** — 에이전트가 작업하면서 새 지식/스킬을 *스스로* 페이지로 추가 (`reference/hermes-agent/`의 skill 자동생성·memory nudge·과거대화 검색 메커니즘 참고).
  - **LLM-위키 방식과 결합** — 고정 6파일이 아니라: 원자 단위 **개념(concept) 페이지** + **엔티티(entity) 페이지** + `_index` + 상호링크 `[[..]]` + `log`(작업 연대기) + `hot`/`hot cache`(최근 자주 쓰는 것). `reference/karpathy-llm-wiki/llm-wiki.md` + OMC `/wiki` 구현을 본으로.
  - 즉 **메모리뱅크 = 살아있는 LLM-위키**가 됨. 세션 바뀌어도 다 기억하고, 쓸수록 두꺼워짐.

### (3) 지식 그래프 = Obsidian 같은 graphify 뷰 — "쌓이는 게 보인다"
- 위 위키(.md 묶음)를 **graphify로 그래프화** → Obsidian 그래프 뷰처럼 노드(개념/엔티티)·엣지(관계)로 시각화.
- 레퍼런스 이미지(`docs/ref-graph-style.png`): "🧠 Cosmic Brain — Knowledge Map (Fibonacci Spiral)" 중심 노드 + `NAVIGATION`/`SOURCES`/`CONCEPTS`/`ENTITIES` 그룹 + `hot`·`log`·`dashboard`·`overview`·`_index` 페이지 + `LLM Wiki Pattern`·`Andrej Karpathy`·`Compounding Knowledge`·`Hot Cache` 노드. ← 우리가 만들 위키 구조와 그래프 모양의 목표 이미지.
- 핵심 효과: **사용자가 자기 에이전트의 "두뇌"가 자라는 걸 눈으로 본다.**

> v1.0에 **포함 안 함**: 멀티채널(Telegram 등), cron, 정교한 스킬 마켓, graphify 풀스택 자동연동의 모든 옵션. → Phase 3+.

---

## 3. "Agentis" — 컨셉

**Agentis = 에이전트가 진화해 나가는 환경/세계의 이름.** (혼돈 → 질서 잡힌 우주.)

부팅 시 에이전트가 하는 일:
1. 사용자에게 **에이전트 이름을 짓게** 한다 ("저는 사내 모델 기반인데, 아직 이름이 없어요.")
2. **명확한 목적**을 함께 정한다 — superpowers식 **clarify 인터뷰** (목적·범위·산출물·제약 몇 질문)
3. **사용법을 안내**한다 (어떻게 일을 시키는지 / 메모리·그래프가 어떻게 자라는지 / 어떻게 같이 크는지)

이후: 세션 넘어 프로젝트를 다 기억, 지식을 위키·그래프로 누적, 반복되는 일은 스스로 스킬로 만들며 진화.

---

## 4. 레퍼런스 → 왜 가져왔나 + 코드 위치

| 레퍼런스 | 정체 | 가져온 이유 | `reference/` 위치 |
|---|---|---|---|
| `cline/cline` (+ 사내 **cline SR**) | 오픈소스 VS Code AI 에이전트. `.clinerules`·워크플로우·MCP·**메모리뱅크**. | **호스트.** 룰(md) 기반 진입점, 메모리뱅크가 출발점. cline SR이 그 사내 버전. | `reference/cline/` |
| `obra/superpowers` | 스킬 기반 방법론. 전부 md 파일. | ① **시작 인터뷰의 clarify 흐름** ② **"md 파일로 워크플로우 구성"** 방식 자체. | `reference/superpowers/` |
| `nousresearch/hermes-agent` | 자기개선 에이전트. 스킬 자동생성·개선, 메모리 nudge, 과거대화 검색. | **메모리뱅크를 스스로 확장**하는 메커니즘(스킬·지식 자가추가) 참고. | `reference/hermes-agent/` |
| `graphify.net` (= `safishamsi/graphify`) | 코드+문서 → 지식 그래프(Tree-sitter+NetworkX+Leiden), D3 force map, Leiden 클러스터, 신뢰도 표시. 무중계·기존 API 키. | **위키를 Obsidian처럼 그래프화** → 지식 쌓이는 게 보이게. | `reference/graphify/` |
| gist(karpathy) **LLM Wiki** | LLM이 직접 유지보수하는 마크다운 KB. 원자 개념 페이지 + 상호링크 + index. ingest·query·lint. | **메모리뱅크를 "고정 파일"에서 "살아있는 위키"로** 바꾸는 패턴. | `reference/karpathy-llm-wiki/llm-wiki.md` |

**합치면:** Cline 룰(md, superpowers식) 위에서 → clarify 인터뷰로 시작 → Cline 메모리뱅크를 Hermes식 자가확장 + LLM-위키 방식으로 진화시켜 "두뇌"로 → graphify로 Obsidian처럼 그래프화. 그 진화 환경 = **Agentis**.

---

## 5. 산출물 = GitHub 레포 내용물 (구조안)

| 경로 | 내용 |
|---|---|
| `seed/` | The Seed — `.clinerules`용 부트스트랩 md(이것 하나로 완결). "안녕" → 인터뷰 → 자가셋업 → 안내. |
| `kit/` | The Kit — clarify 인터뷰 스크립트, 워크플로우 md들, 스킬 md들, 메모리뱅크(살아있는 LLM-위키) 스캐폴드, 그래프 뷰어. |
| `kit/memory/` | 메모리뱅크 시드: `_index.md`, `overview.md`, `log.md`, `hot.md`, `concepts/`, `entities/` (+ `[[..]]` 링크 규약 문서). |
| `kit/graph/` | graphify 연동 설정 + (또는) 정적 D3 HTML 뷰어 + 메모리.md→노드/엣지 JSON 추출 스크립트. |
| `docs/` | Agentis 컨셉, 사내 도입 안내(비개발 직무 톤), 에이전트 예시 카탈로그(규격인증 문서 자동화 / 개발 디버깅 / …), `ref-graph-style.png`. |
| `examples/` | 예제 에이전트(가능하면 "규격인증 문서 자동화" 류). |
| `PLAN.md` / `README.md` | 기획서(v0.4) / 소개. |
| `reference/` | 참고용 원본 레포 클론 — **깃이그노어, 커밋 안 함**. |

---

## 6. 동작 시나리오 (해피 패스)

1. 동료가 작업 폴더에 Agentis `kit/`을 복붙(또는 룰 파일 1개만). `.clinerules`가 `seed/` 부트스트랩 md를 가리킴.
2. 동료가 **"안녕"**.
3. 에이전트: *"안녕하세요. 저는 사내 모델 기반이고 아직 이름이 없어요. 이름을 지어주세요. 그리고 어떤 업무를 도울까요?"* → **clarify 인터뷰**.
4. 에이전트가 **정체성 md** + **메모리뱅크 시드**(`memory/_index.md`, `overview.md`, …)를 자가 생성하고 인터뷰 결과 기록.
5. **사용법 3줄 안내**.
6. 이후 매 작업: 업무 처리 → 새로 안 것을 `concepts/`·`entities/` 페이지로 추가하고 `_index`·`log`·`hot` 갱신 → 그래프 갱신 → (반복되는 일이면) *"이거 스킬 md로 만들어 둘까요?"* 제안.
7. **새 세션**: 메모리뱅크 위키를 먼저 읽고 *"지난번 ○○까지 했었죠. 이어서?"* — 잊지 않음. 그래프 보면 두뇌가 자란 게 보임.

**첫 사용자 = 우리 파트 동료들** (규격인증 문서 자동화 에이전트 / 개발 디버깅 에이전트 / 등 다양) → 인터뷰 질문지·예시 카탈로그를 이 폭에 맞춤.

---

## 7. 단계 (phased)

- **Phase 0 (완료/진행)** — ① GitHub `imejaim/agentis` 생성·public 전환·푸시 ✅ ② `reference/` 5개 클론 ✅ ③ 그래프 레퍼런스 이미지 확보 ✅. (cline SR 환경 실측은 **추후로 미룸** — v1.0은 "표준 Cline" 가정으로 진행.)
- **Phase 1 (v1.0 MVP)** — ① **The Seed v1**: 부트스트랩 + clarify 인터뷰 + 정체성/메모리뱅크 자가셋업 + 안내. ② **메모리뱅크 = 살아있는 LLM-위키** 스캐폴드 + 운영 규약(언제 페이지 추가/갱신/링크). ③ **graphify 연동 or 정적 D3 뷰어**로 Obsidian식 그래프. ④ 예제 에이전트 1개 dogfood.
- **Phase 2** — 스킬 라이브러리 확충, 워크플로우 템플릿, 메모리 위키 lint(모순·낡음 정리), 경로 A("이거 보고 셋팅해줘") 다듬기.
- **Phase 3** — Hermes식 학습 루프 본격화(스킬 자동생성·개선·nudge·과거대화 검색), graphify 풀 연동(신뢰도/커뮤니티/신노드 강조), cline SR 환경 실측 후 사내 맞춤.
- **Phase 4** — 사내 확산: 온보딩 문서 + 동료별 파일럿 + 피드백 반영.

---

## 8. 설계 원칙

- **전부 md** — 룰·인터뷰·워크플로우·스킬·메모리, 다 markdown. 빌드 없음. cline SR 제약에 강함.
- **셋팅 최소 / 자가 부트스트랩** — 이상은 "파일 1개 + 안녕". 에이전트가 자기 구조를 스스로 만든다.
- **두뇌 우선** — 메모리뱅크=살아있는 위키가 1급 시민. "잊지 않는 것" + "쓸수록 두꺼워지는 것"이 핵심 가치. 카오스 → 유니버스.
- **보이게 한다** — graphify 그래프로 지식 성장이 *시각적으로* 드러나야 함. (사용자 동기부여 + 공진화의 가시화)
- **공진화** — 사용 = 학습. 사용자 역량과 에이전트 지식·스킬을 동시에 키운다.
- **무중계 / portable** — 사용자 기존 API 키, 외부 중계 없음(graphify 철학). 사내 보안 친화.

---

## 9. 열린 이슈 / 나중에

- cline SR에서 룰/워크플로우/hook/skill이 실제로 어디까지 되는지 — **추후 실측**(대표님이 사내에서). v1.0은 표준 Cline 가정.
- 그래프 뷰를 cline SR 안에서 어떻게 띄울지(VS Code webview vs 외부 HTML vs Obsidian 자체) — 실측 후 결정. 일단 정적 HTML 한 장 가정.
- graphify가 Python 패키지(`pyproject.toml`) — 사내에서 pip 설치 가능한지 확인 필요. 안 되면 "메모리.md → JSON → D3 HTML" 경량 자작 경로.
- 멀티채널·cron·스킬 마켓 — Phase 3+.

---

## 10. 대표님 확인 ❓ (거의 없음)

1. v1.0 범위(§2) 이대로 OK? 빠지거나 더할 것?
2. 레포 구조안(§5) — `seed/` / `kit/` / `docs/` / `examples/` 네이밍 OK?
3. (선택) graphify를 v1.0에 정식 연동 vs v1.0은 경량 자작 뷰어 + graphify는 Phase 3 — 어느 쪽 선호? (사내 pip 설치 가능성과도 연결)

---

## 11. 코부장 다음 행동

1. ✅ public 전환, `docs/ref-graph-style.png` 추가, PLAN v0.4.
2. ⏭️ **The Seed v1 초안** — `seed/` 부트스트랩 md (인터뷰·자가셋업·안내) + `.clinerules` 엔트리.
3. clarify 인터뷰 스크립트 — `reference/superpowers/skills/` brainstorming 스킬 코드 분석 → 업무 에이전트용 각색.
4. 메모리뱅크=살아있는 LLM-위키 스캐폴드 & 운영규약 — `reference/karpathy-llm-wiki/llm-wiki.md` + Cline 메모리뱅크 구조 + OMC `/wiki` 참고.
5. 그래프 뷰 PoC — 메모리 .md → 노드/엣지 JSON → 정적 D3 HTML(Obsidian풍). graphify 임베드 가능성 병행 조사.

---

*— 코부장. §10 답 없으면 §2 범위 그대로 The Seed v1 초안 들어갑니다.*
