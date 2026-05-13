# 예제: 규격인증 문서 자동화 에이전트 "규격이"

Agentis로 만든 업무처리 에이전트가 **몇 번 일한 뒤** 어떤 모습이 되는지 보여주는 예제입니다.
(실제 사내 자료가 아니라 — 구조를 보여주려고 만든 가상의 내용입니다.)

- 도메인: 전자제품 규격인증(KC/RoHS 등) 제출 문서 검토
- 에이전트가 하는 일: ① 제출 문서 목록 ↔ 요구 체크리스트 대조(누락 찾기) ② 시험성적서에서 항목 추출 → 표 정리, 둘 다 **Python으로 처리 + 검증**

## 안에 뭐가 있나

```
agentis/
  agent.md                         ← "규격이"의 정체성 (인터뷰 결과로 채워진 상태)
  memory/                          ← 두뇌 — 몇 번 일하며 쌓인 위키
    _index.md  overview.md  log.md  hot.md
    concepts/  entities/  sources/  ← 개념·엔티티·소스 페이지들 ([[링크]]로 연결됨)
  skills/checklist-대조/            ← 반복 작업이 스킬로 승격된 예 (SKILL.md + run.py)
  workflows/시험성적서-항목추출.*    ← 워크플로우 + 결정론 스크립트
  graph/build_graph.py             ← 두뇌 그래프 빌더
  sample-data/                     ← run.py 들을 돌려볼 수 있는 샘플 입력
```

## 돌려보기

```bash
cd examples/spec-doc-checker

# 1) 두뇌 그래프 빌드 → 브라우저로 열기
python agentis/graph/build_graph.py --open

# 2) 체크리스트 대조 스킬 (샘플 데이터)
python agentis/skills/checklist-대조/run.py \
    --checklist agentis/sample-data/요구체크리스트.txt \
    --submitted agentis/sample-data/제출문서목록.txt \
    --out agentis/sample-data/대조결과.md

# 3) 시험성적서 항목 추출 워크플로우
python agentis/workflows/시험성적서-항목추출.py \
    --in agentis/sample-data/시험성적서-모델X.txt \
    --out agentis/sample-data/항목표.csv
```

> 이건 "결과물 예시"이지 키트가 아닙니다. 새 에이전트를 만들려면 루트의 `seed/` + `kit/` 을 쓰세요.
