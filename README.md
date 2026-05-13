# Agentis

> 사내 **VS Code + cline SR** 환경에서, **워크스페이스 룰 파일 하나**로 부팅되는 **업무처리 에이전트 키트**.
> 카오스 → 유니버스. 쓰는 사람도 크고, 에이전트도 큰다.

## 이게 뭔가요

Agentis는 "에이전트를 만드는 에이전트 환경"입니다. 동료가 자기 작업 폴더에 씨앗 파일 하나 넣고 클라인에게 **"안녕"** 한 마디만 하면:

1. 에이전트가 **이름을 지어달라**고 합니다.
2. 짧은 **clarify 인터뷰**로 "무슨 업무를 도울지" 함께 정하고, 설계 요약을 보여주고 승인받습니다.
3. 자기 **정체성·기억(brain)** 구조(`agentis/`)를 스스로 만들고 **사용법을 안내**합니다.
4. 이후 일하면서 — 가능한 건 **Python 코드로 짜서 검증**하고(정확성·신뢰성 우선), 배운 것이 **위키 + 지식 그래프**로 쌓이고, 반복되는 일은 **스스로 스킬로** 만들며 진화합니다.
5. 세션이 바뀌어도 **그 프로젝트를 다 기억**합니다.

목적은 코딩 에이전트도 개인 비서도 아닌 **업무처리 에이전트** — 그리고 동료들이 "에이전틱하게 일한다는 게 뭔지" 직접 체험하게 하는 것.

## 써보기

**A. 가장 간단히 (씨앗만)**
1. cline SR 쓸 작업 폴더에 `.clinerules` 파일을 만들고 [`seed/agentis.md`](./seed/agentis.md) 내용을 그대로 붙여넣기. (또는 `.clinerules/agentis.md` 로 저장)
2. Cline 대화창에 **`안녕`**.
3. 인터뷰 → 승인 → 에이전트가 `agentis/` 폴더(정체성·메모리·스킬·워크플로우·그래프)를 스스로 생성 → 사용법 안내 → 첫 업무.
4. 일 시키고, 끝나면 `python agentis/graph/build_graph.py --open` 으로 두뇌 그래프 보기. 세션 닫았다 다시 열어도 다 기억함.

**B. 더 갖춰서 (키트까지)**
1. [`kit/agentis-template/`](./kit/agentis-template/) 폴더를 작업 폴더에 **`agentis/`** 라는 이름으로 통째로 복사.
2. 위 A의 1~2번 동일. 에이전트가 빈 템플릿을 인터뷰 결과로 채움.

**C. 먼저 구경 (예제)**
- [`examples/spec-doc-checker/`](./examples/spec-doc-checker/) — 규격인증 문서 자동화 에이전트 "규격이"가 며칠 일한 모습.
  ```bash
  cd examples/spec-doc-checker
  python agentis/graph/build_graph.py --open      # 두뇌 그래프 (브라우저로 열림)
  python agentis/skills/checklist-대조/run.py --checklist agentis/sample-data/요구체크리스트.txt --submitted agentis/sample-data/제출문서목록.txt --out agentis/sample-data/대조결과.md
  python agentis/workflows/시험성적서-항목추출.py --in agentis/sample-data/시험성적서-모델X.txt --out agentis/sample-data/항목표.csv
  ```
  > 자세한 설치는 [`seed/README.md`](./seed/README.md), 키트 설명은 [`kit/README.md`](./kit/README.md), 계획은 [`PLAN.md`](./PLAN.md) (현재 v0.6).

## v1.0 핵심

- ⓪ **결정론 우선** — 사내 에이전트라 정확성·신뢰성이 최우선. 업무처리는 최대한 **Python 코드**로 짜서 재실행·검증 가능하게. (md = 지식·규약, py = 실제 처리)
- ① **Cline 룰(md 파일) 기반**으로 동작 — superpowers처럼, 빌드·설치 의존 없음
- ② **Cline 메모리뱅크 → 살아있는 LLM-위키** — Hermes식 자가확장 + LLM-위키 방식으로 진화시켜 "두뇌"로 (`agentis/memory/`)
- ③ **Obsidian처럼 그래프화** → 지식 쌓이는 게 눈에 보이게. `agentis/graph/build_graph.py` 가 자체완결형 `graph.html` 생성 (외부 의존 0 — 사내망/오프라인 OK). graphify 본체 연동은 추후. (목표 스타일: [`docs/ref-graph-style.png`](./docs/ref-graph-style.png))

## 레포 구조

| 경로 | 내용 |
|---|---|
| `seed/agentis.md` | The Seed — `.clinerules` 로 넣는 부트스트랩 커널 (이것 하나로 완결) |
| `seed/README.md` | 씨앗 설치 가이드 |
| `kit/agentis-template/` | 작업 폴더에 `agentis/` 로 복사하는 템플릿 (agent 템플릿 / memory 스캐폴드+운영규약 / skills·workflows 포맷 / `build_graph.py`) |
| `kit/README.md` | 키트 사용법 |
| `examples/spec-doc-checker/` | 예제 에이전트 "규격이" — 채워진 `agentis/` + 동작하는 `run.py` 2종 + 샘플 데이터 |
| `docs/` | `ref-graph-style.png` (목표 그래프 스타일). 컨셉·도입 문서는 추후 |
| `PLAN.md` | 기획서 (v0.6) |
| `reference/` | 참고용 원본 레포 클론 — **깃이그노어, 커밋 안 함** |

## 영감을 준 것들

- [cline/cline](https://github.com/cline/cline) — 호스트 플랫폼 (cline SR의 베이스)
- [obra/superpowers](https://github.com/obra/superpowers) — 시작 인터뷰의 clarify 흐름, "md = 워크플로우" 구조
- [nousresearch/hermes-agent](https://github.com/nousresearch/hermes-agent) — 세션 넘는 기억 + 스킬 자가 진화
- [graphify](https://graphify.net/) ([safishamsi/graphify](https://github.com/safishamsi/graphify)) — 지식 그래프 시각화 ("두뇌")
- [Karpathy — LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — LLM이 직접 유지보수하는 지식베이스
- [지식 그래프 실사용기 (brunch)](https://brunch.co.kr/@abrahamsong/164)

## 상태

**v1.0 일차 구현 완료** — 씨앗(`seed/agentis.md`) · 키트(`kit/agentis-template/`) · 그래프 빌더(`build_graph.py`, 테스트 통과) · 예제 에이전트(`examples/spec-doc-checker/`, 스크립트 동작 확인). 다음: cline SR 환경에서 실제로 돌려보고 보강. 진행 상황은 [`PLAN.md`](./PLAN.md).
