# CHANGELOG — v1.4 → v1.5

> 작성: 코부장 / 2026-05-26. v1.5 보강 세션 전체 변경 사항 정리.

---

## 요약 (한 줄)

딥인터뷰 분기 + 캐릭터 빌보드 + 업무 다이어그램 + Graph RAG 두뇌 인덱스 + 사내깃 자동 푸시 + 홀로노믹 통합 + 온보딩 가이드 보강.

---

## 변경 파일 목록

### 씨드 (seed/)

| 파일 | 변경 내용 | 라인 증감 |
|---|---|---|
| `seed/agentis.md` | 헤더 v1.4 → v1.5. §1-2.5 딥인터뷰 분기 신규(기존 agentis/ 감지 시 스킵). §3-5 Hermes 자가진화 보강. §3-7 자가 도태·lint 신규. §5-6 Level≥5 자동 안내 추가. | +74 줄 |
| `seed/README.md` | 첫 줄 강조 문구 + 추천 방법 마킹(`★ 추천`). | +10 줄 |
| `seed/build-html.py` | 기본 출력 경로 → `docs/agentis-view.html`. | +11 줄 |

### 키트 (kit/agentis-template/)

| 파일 | 변경 내용 | 라인 증감 |
|---|---|---|
| `.kit-version` | `seed:1.5 / kit:1.5` 로 갱신. | -1/+1 |
| `agent.template.md` | `character:` 필드 추가(코부장/오과장/젬대리 선택). | +1 줄 |
| `graph/build_graph.py` | v1.5 캐릭터 빌보드: THREE.Sprite + data URI SVG + sin wave bob + 활성 노드 lerp 추적. | +192 줄 |
| `graph/build_flow.py` | **신규** — n8n 스타일 업무 다이어그램. 590줄. stdlib only. | +590 줄 |
| `graph/flow.html` | build_flow.py 산출물 샘플. | 신규 |
| `memory/_brain/build_brain_index.py` | **신규** — SQLite+FTS5 두뇌 인덱스 빌더. 374줄. | +374 줄 |
| `memory/_brain/query_brain.py` | **신규** — 4모드(hybrid/keyword/semantic/graph) + RRF 병합. 389줄. | +389 줄 |
| `memory/_brain/ingest_knowledge.py` | **신규** — 메타 자동추출 + 지식 수집기. 538줄. | +538 줄 |
| `memory/_brain/README.md` | **신규** — Brain 인덱스 사용법 가이드. | +60 줄 |
| `memory/_brain/holonomic.md` | **신규** — OffSpace-Self-Growth-Agent 통합 7절. | +120 줄 |
| `workflows/사내깃-올리기.py` | **신규** — 591줄. 5모드(--check/--push/--status/--log/--config). Level≥5 자동 안내 게이트. | +591 줄 |
| `workflows/skill-도태.py` | **신규** — 스킬 도태 결정론 워크플로우. | 신규 |
| `workflows/skill-도태.workflow.md` | **신규** — 스킬 도태 md 설명. | 신규 |
| `workflows/memory-lint.py` | **신규** — 깨진 링크·고아 페이지 검사. | 신규 |
| `workflows/memory-lint.workflow.md` | **신규** — memory-lint md 설명. | 신규 |

### Cline 룰 (.clinerules/)

| 파일 | 변경 내용 |
|---|---|
| `.clinerules/agentis.html` | **삭제** — html 뷰어 제거. |
| `.clinerules/agentis.md` | **신규** — `seed/agentis.md` 와 동일 내용 재설치. Cline 워크스페이스 룰로 직접 사용. |

### 예제 (examples/spec-doc-checker/)

| 파일 | 변경 내용 |
|---|---|
| `agentis/agent.md` | `character: 코부장` 필드 추가. |
| `agentis/graph/build_graph.py` | kit v1.5 동기화(캐릭터 빌보드 적용). |
| `agentis/graph/build_flow.py` | **신규** — kit 동기화. |
| `agentis/graph/flow.html` | **신규** — build_flow 산출물. |
| `agentis/graph/graph.html` | v1.5 빌드 결과 갱신. |
| `agentis/graph/graph.json` | 노드/링크 갱신(24노드/76링크). |
| `agentis/memory/stats.md` | 능력치 갱신(Level 7 / XP 800). |
| `agentis/memory/_brain/` | **신규** — brain.sqlite + 빌더/쿼리 스크립트 동기화. |
| `agentis/workflows/memory-lint.py` | **신규** — kit 동기화. |
| `agentis/workflows/memory-lint.workflow.md` | **신규** — kit 동기화. |
| `agentis/workflows/skill-도태.py` | **신규** — kit 동기화. |
| `agentis/workflows/skill-도태.workflow.md` | **신규** — kit 동기화. |

### 문서 (docs/)

| 파일 | 변경 내용 |
|---|---|
| `docs/agentis-view.html` | **신규** — seed/build-html.py 산출물. |
| `docs/배포-사내깃허브.md` | **신규** — 실용 가이드 + 상세 전략. |
| `docs/CHANGELOG-v1.5.md` | **이 파일**. |

### 루트

| 파일 | 변경 내용 |
|---|---|
| `README.md` | 상단 "잠깐 — 만들지 마세요" + 3분 셋업 + "공유 = 브랜치" 섹션 추가. +35줄. |
| `PLAN.md` | v0.10 → v0.11. §7 Phase 1.5 추가, §10 결정 7개 추가, §11 항목 12~23 갱신. |

### 레퍼런스 (reference/ — gitignore, 커밋 안 됨)

- `reference/omx` 클론
- `reference/ouroboros` 클론
- `reference/OffSpace-Self-Growth-Agent` 클론 (holonomic.md 원본 출처)

---

## 검증 결과 (examples/spec-doc-checker 기준)

| 명령 | 첫 줄 출력 | 결과 |
|---|---|---|
| `python agentis/graph/build_graph.py` | `[build_graph] root=...spec-doc-checker\agentis` | ✅ 24노드/76링크/캐릭터 적용 |
| `python agentis/graph/build_flow.py` | `[build_flow] root=...spec-doc-checker\agentis` | ✅ flow.html 15KB 생성 |
| `python agentis/graph/agent-stats.py` | `Level: 7  XP: 800  생일: 2026-05-07 (19일째)` | ✅ |
| `python agentis/memory/_brain/build_brain_index.py` | `[build_brain_index] root=... files=14 domain_vocab=41` | ✅ brain.sqlite 생성 |
| `python agentis/memory/_brain/query_brain.py "체크리스트" --mode keyword --pretty` | `질문: 체크리스트 / 모드: keyword` | ✅ 1건 반환 |
| `python agentis/workflows/memory-lint.py` | `# memory-lint 보고서` | ✅ 깨진 링크 0 |
| `python agentis/workflows/사내깃-올리기.py --check` (kit 기준) | `[사내깃] agent.md 파일 찾는 중...` | ✅ main_repo 미설정 안내 |

---

## v1.4 → v1.5 업그레이드 하는 법

기존에 `agentis/` 폴더가 있는 작업 폴더를 v1.5로 올리는 방법:

```bash
# 1. 씨드 업그레이드 확인 (변경된 절 목록)
python agentis/workflows/씨드-업그레이드.py --check

# 2. 선택적 적용 (특정 절만)
python agentis/workflows/씨드-업그레이드.py --apply --plan

# 3. 새 두뇌 인덱스 빌드
python agentis/memory/_brain/build_brain_index.py

# 4. 새 워크플로우 복사 (kit에서)
# kit/agentis-template/workflows/ 의 신규 파일을 agentis/workflows/ 에 복사
```

`agent.md` 에 `character:` 필드가 없으면 `코부장` 이 기본값으로 적용됩니다.

---

## 다음 사용자 액션

| 옵션 | 내용 |
|---|---|
| **A. 커밋 진행** | 위 검증 모두 PASS → `git add` + `git commit` 진행 요청 |
| **B. 추가 작업** | examples에 `사내깃-올리기.py` 동기화, seed/agentis.md `.clinerules/agentis.md` 내용 일치 확인 |
| **C. 보류** | 사내 환경 테스트 먼저 → 피드백 받고 v1.5.1 패치 후 커밋 |

> 추천: **A** — 검증 7종 모두 통과. 커밋 메시지 초안은 아래 참고.

---

## 커밋 메시지 초안

```
feat: v1.5 — 딥인터뷰 분기 + 캐릭터 빌보드 + Graph RAG + 사내깃 + 홀로노믹 통합

씨드: §1-2.5 딥인터뷰 분기, §3-5 Hermes 자가진화 보강, §3-7 자가 도태/lint, §5-6 Level≥5 자동 안내.
키트 그래프: build_graph.py v1.5 캐릭터 빌보드(SVG data URI + sin bob + 활성 노드 lerp 추적),
             build_flow.py 신규(n8n 스타일 업무 다이어그램, 590줄, stdlib only).
키트 두뇌: memory/_brain/ — build_brain_index.py(SQLite+FTS5, 374줄),
           query_brain.py(hybrid/keyword/semantic/graph + RRF, 389줄),
           ingest_knowledge.py(538줄), holonomic.md(OffSpace 통합 7절).
키트 워크플로우: 사내깃-올리기.py(591줄, Level≥5 자동 안내), skill-도태.py, memory-lint.py.
온보딩: README 상단 "잠깐 만들지 마세요" + 3분 셋업, docs/배포-사내깃허브.md.
PLAN v0.10 → v0.11.
```
