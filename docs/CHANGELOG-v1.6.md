# CHANGELOG — v1.5 → v1.6

> 작성: 코부장 / 2026-05-29. v1.6 빌드 전체 변경 사항 정리.

---

## 요약 (한 줄)

사내 활발 사용 중 발견된 두 가지 문제 해결 — ① 주요 업무 ≠ 부수 업무 구분 불명확, ② 설치 마찰.

---

## 변경 파일 목록

### 씨드 (seed/)

| 파일 | 변경 내용 | 라인 증감 |
|---|---|---|
| `seed/agentis.md` | 헤더 v1.5 → v1.6. §1-2 주요 업무 3-5개 명시 강화. §1-2.6 "주요 업무 정의 (primary_tasks)" 신규 (라인 127~145). §3-1 분류 한 줄 추가. §3-4 log.md 컨벤션 `[primary:N]`/`[aux]` 태그 확장. local-mods 갱신. | +35 줄 |
| `.clinerules/agentis.md` | seed/agentis.md 와 sha256 동기화 (`938397e6...`). | 동기화 |
| `docs/agentis-view.html` | seed/build-html.py 재생성 (72KB). | 재생성 |

### 키트 (kit/agentis-template/)

| 파일 | 변경 내용 | 라인 증감 |
|---|---|---|
| `.kit-version` | `seed:1.6 / kit:1.6` 으로 갱신. | -1/+1 |
| `agent.template.md` | `## 주요 업무 (primary_tasks)` YAML 섹션 신규 추가. | +12 줄 |
| `graph/build_flow.py` | **전면 리라이트** — 스윔레인 + 대시보드 + 5색. `[primary:N]` 태그 감지해 주요 업무 레인 분리. | 전면 리라이트 |
| `graph/agent-stats.py` | "주요 업무 처리율" 섹션 + 항목별 카운트 추가. | +30 줄 |

### 예제 (examples/spec-doc-checker/)

| 파일 | 변경 내용 |
|---|---|
| `agentis/agent.md` | `primary_tasks:` 4개 예시 추가. |
| `agentis/memory/log.md` | `[primary:N]` 태그 박힌 데모 데이터 추가. |

### 인스톨러 (루트)

| 파일 | 변경 내용 | 라인수 |
|---|---|---|
| `install.py` | **신규** — 결정론 인스톨러. stdlib only, 7옵션(`--target`/`--here`/`--dry-run`/`--force`/`--no-kit`/`--quiet`/`--version`), UTF-8 안전. | 388 줄 |
| `install.bat` | **신규** — Windows 더블클릭용 래퍼. | 5 줄 |
| `install.sh` | **신규** — Mac/Linux 래퍼. | 6 줄 |

### 사내 깃 URL (kit/agentis-template/workflows/ + docs/)

| 파일 | 변경 내용 |
|---|---|
| `kit/agentis-template/workflows/사내깃-올리기.py` | `--init` 모드 안내 메시지에 삼성 사내 표준 URL 패턴 예시 추가. |
| `docs/배포-사내깃허브.md` | 정본 사내 미러 URL `github.sec.samsung.net/dongho-yoon/agent_seed` 명시. |

### 문서 (docs/)

| 파일 | 변경 내용 |
|---|---|
| `docs/CHANGELOG-v1.6.md` | **이 파일**. |

### 루트

| 파일 | 변경 내용 |
|---|---|
| `README.md` | "사내 동료 설치" 섹션 (라인 28~62) — A 더블클릭 / B cline 지시문 / C 직접 명령. `git clone https://github.sec.samsung.net/dongho-yoon/agent_seed` URL 명시. |
| `PLAN.md` | v0.11 → v0.12. §7 Phase 1.6 추가, §10 결정 3개 추가(사내깃/주요업무/인스톨러), §11 항목 24 추가. |

---

## 검증 결과 (examples/spec-doc-checker 기준)

| 명령 | 첫 줄 출력 | 결과 |
|---|---|---|
| `python agentis/graph/build_flow.py` | `[build_flow] root=...spec-doc-checker\agentis` | ✅ 스윔레인 flow.html 생성, 주요 업무 처리율 50% |
| `python agentis/graph/agent-stats.py` | `Level: 7  XP: 800  생일: 2026-05-07` | ✅ 주요 업무 처리율 섹션 출력 |
| `python install.py --dry-run --here` | `[install] dry-run 모드` | ✅ 4 시나리오(신규/기존/force/no-kit) 모두 정상 |
| `python -m py_compile install.py` | (오류 없음) | ✅ syntax 이상 없음 |

---

## v1.5 → v1.6 업그레이드 하는 법

### 기존 사용자 (이미 `agentis/` 가 있는 작업 폴더)

```bash
# 1. 씨드 업그레이드 확인 (변경된 절 목록)
python agentis/workflows/씨드-업그레이드.py --check

# 2. §1-2.6 신규 절 받기 (action: take)
python agentis/workflows/씨드-업그레이드.py --apply --plan plan.json

# 3. agent.md 에 primary_tasks 채우기 (인터뷰로 3-5개 정의)
# agent.md 의 ## 주요 업무 (primary_tasks) 섹션을 직접 편집하거나
# 에이전트에게 "주요 업무 정의해줘" 라고 말하기

# 4. build_flow.py 재실행 (스윔레인 확인)
python agentis/graph/build_flow.py
```

### 새 사용자 (처음 설치)

```bash
# 사내 agent_seed 에서 받기
git clone https://github.sec.samsung.net/dongho-yoon/agent_seed

# Windows: 더블클릭
install.bat

# Mac/Linux:
bash install.sh

# 또는 직접 명령
python install.py --target "C:\내작업\프로젝트A"
```

설치 완료 후 VS Code 에서 작업 폴더 열고 Cline 에 `안녕` → 인터뷰 시작.

---

## 커밋 메시지 초안

```
feat: v1.6 — 주요 업무 정의 + 인스톨러 + 사내 깃 URL 확정

씨드: §1-2.6 "주요 업무 (primary_tasks) 3-5개 정의" 신규,
       §1-2/§3-1/§3-4 보강(분류 + [primary:N]/[aux] 태그).
키트 시각화: build_flow.py 전면 리라이트 — N개 주요 업무 스윔레인 + 대시보드 + 5색,
             agent-stats.py 에 "🎯 주요 업무 처리율" + 항목별 카운트.
인스톨러: install.py(388줄, stdlib only) + install.bat + install.sh —
         결정론 단일 명령, cline 자율성 차단. README "사내 동료 설치" 섹션.
사내 깃: agent_seed = github.sec.samsung.net/dongho-yoon/agent_seed 확정.
PLAN v0.11 → v0.12.
```
