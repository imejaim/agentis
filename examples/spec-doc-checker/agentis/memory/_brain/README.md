# memory/_brain/ — 두뇌 인덱스 + Graph RAG

`memory/` 의 마크다운들을 **SQLite 인덱스 + 시맨틱 임베딩 캐시 + 그래프 1-hop 확장**으로 묶은 두뇌의 *검색·회상* 계층입니다. `graph/build_graph.py` 가 "노드/엣지" 만 보여줬다면, 이쪽은 그 위에 **내용 검색(BM25) + 메타데이터 + 의미 검색**을 얹어 "기억해 — 이 질문에 관련된 페이지 5개" 가 결정론적으로 나오게 합니다.

> 결정론 우선. 외부 AI API 안 씁니다. 로컬 임베딩(`sentence-transformers`)이 1순위이고, 그것도 없으면 BM25 + 그래프만으로 동작합니다.

## 어떻게 동작하나 (한 페이지)

```
agentis/memory/**/*.md
        │
        ▼  (build_brain_index.py — stdlib only)
brain.sqlite
  ├ pages(id, path, title, category, tokens, created_at, updated_at, content_hash)
  ├ tags(page_id, tag)               ← frontmatter 의 tags:
  ├ links(src_id, dst_path, anchor)  ← [[..]] 위키링크
  ├ domains(page_id, domain)         ← agent.md 도메인 사전 + 태그
  ├ entities(page_id, entity_name, entity_type)  ← entities/ + 본문 정규식
  └ pages_fts(path, title, body)     ← FTS5 (BM25)
        │
        ▼  (query_brain.py)
질문 "<자연어>"
  ├ keyword (FTS5 BM25)               ← 항상 동작
  ├ semantic (sentence-transformers + FAISS)  ← 패키지 가용 시
  ├ RRF 결합 (Reciprocal Rank Fusion)
  └ graph 1-hop 확장 (graph.json 의 엣지)
        │
        ▼
{ "results": [ {path, title, score, snippet, neighbors[]}, ... ] }
```

## 명령 (실제 예시)

```bash
# 1) 인덱스 빌드 — memory/ 가 바뀔 때마다
python agentis/memory/_brain/build_brain_index.py

# 2) 질문 — 키워드 모드 (항상 동작)
python agentis/memory/_brain/query_brain.py "규격 인증 절차" --mode keyword

# 3) 질문 — 하이브리드 + 사람용 출력
python agentis/memory/_brain/query_brain.py "체크리스트 누락 검출" --pretty

# 4) 자료 → 두뇌 ingest (메타데이터 자동 추출 + 페이지 생성)
python agentis/memory/_brain/ingest_knowledge.py --file 자료.pdf
python agentis/memory/_brain/ingest_knowledge.py --dir 받은-자료들/

# 5) 가용성 점검
python agentis/memory/_brain/query_brain.py --check
```

## 가용 패키지

| 패키지 | 용도 | 필수? |
|---|---|---|
| `sqlite3` (stdlib) | 인덱스 | ✅ 표준 |
| `sentence-transformers` | 의미 검색 | 선택 — 없으면 keyword + graph 로 폴백 |
| `faiss-cpu` | 빠른 NN 검색 | 선택 — 없으면 numpy 코사인으로 폴백 |
| `numpy` | 임베딩 텐서 | semantic 쓰려면 필요 |
| `pypdf` 또는 `PyPDF2` | PDF ingest | 선택 — 없으면 PDF 건너뜀 |
| `python-docx` | DOCX ingest | 선택 — 없으면 DOCX 건너뜀 |

추천 설치 (사내망에서 가능하면):
```
pip install sentence-transformers faiss-cpu numpy pypdf python-docx
```

모델은 `paraphrase-multilingual-MiniLM-L12-v2` (~117MB, 한국어 포함 50개 언어). 한 번 다운로드되면 `~/.cache/huggingface/` 에 캐시되어 오프라인에서도 동작합니다.

## 결과물

- `brain.sqlite` — 인덱스 본체 (build_brain_index.py 가 매번 새로 생성).
- `embeddings.npy` + `ids.json` — 임베딩 캐시 (query_brain.py 첫 semantic 호출 시 생성).
- `holonomic.md` — 홀로노믹 브레인 컨셉 노트 (왜 페이지들이 분산·자기유사적인지).

## 워크플로우 (사용자가 일상에서 도는 루프)

1. **자료 받음** → `ingest_knowledge.py --file <자료>` → `memory/sources/<날짜>-<이름>.md` 생성 + 새 엔티티/개념 스텁.
2. **인덱스 갱신** → `build_brain_index.py` → `brain.sqlite` 다시 빌드.
3. **그래프 갱신** → `python agentis/graph/build_graph.py` (기존). 두뇌 그래프에 신규 노드 표시.
4. **질문** → `query_brain.py "<질문>" --pretty` → 관련 페이지 5개 + 이웃.
5. **사용자가 자동 스텁 읽고 채움** — `auto-stub` 태그가 박혀 있어서 나중에 찾기 쉬움.

## 정확성 / 검증 포인트

- 인덱스 빌더는 **결정론**. 같은 입력 → 같은 brain.sqlite (content_hash 일치).
- semantic 결과가 keyword 와 모순될 때는 RRF 가 양쪽 신호를 합쳐 robust 하게 가져갑니다.
- 그래프 1-hop 은 *링크가 있을 때만* 작동 — `[[..]]` 링크가 없는 페이지는 신뢰성 점수가 낮아짐(메모리 lint 가 잡아냄).

## 한계 / 알려진 이슈

- FTS5 토크나이저는 한국어 형태소 분석 X — 단어 단위 매칭. (사내에서 KoNLPy 가능하면 v1.6 후보.)
- 엔티티 추출은 정규식 폴백. 정확한 NER 은 LLM hook (선택) 통해 보강하세요.
- pdf/docx 가 사내망에서 설치 불가하면 텍스트로 미리 변환 후 ingest.

자세한 컨셉은 `holonomic.md` 참고.
