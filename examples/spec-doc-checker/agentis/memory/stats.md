---
type: stats
updated: 2026-05-26
auto: true
---

# 🧬 규격이 — Character Sheet

> 능력치는 `agentis/` 파일에서 자동 산출됩니다 (`python agentis/graph/agent-stats.py`). 진화하는 모습이 눈에 보이도록.

## 요약
- **Level**: 7  ·  **XP**: 800
- **생일**: 2026-05-07  ·  **나이**: 19일
- **효율(작업/1k 토큰)**: (토큰 미기록)

## 능력치

| 능력 | 값 | 설명 |
|------|----|----|
| ⚡ Speed | **9** | 스킬 + 워크플로우 (가진 도구) |
| 🧠 INT | **39** | 메모리 페이지 + 그래프 연결성 |
| 🎨 Variety | **13** | 작업 종류 + 태그 다양성 |
| 💪 Stamina | **19** | 생존일수 |
| 🦉 Wisdom | **0** | 정비(lint) + 개념 추상화 |

## 작업 내역 (`memory/log.md` 집계)

| 종류 | 수 |
|------|----|
| task   | 1 |
| ingest | 1 |
| skill  | 1 |
| lint   | 0 |
| note   | 1 |
| setup  | 1 |

## 보유 자원

- 스킬: **1** (`skills/<이름>/SKILL.md`)
- 워크플로우: **8** (`workflows/*.workflow.md`)
- 메모리 페이지: **14** (개념 3 / 엔티티 3 / 소스 2)
- 그래프: 노드 24 / 엣지 76

## 🧬 감지된 도메인 유전자 (상위 태그)

- `시험성적서`  ×3
- `인증`  ×2
- `kc`  ×2
- `rohs`  ×1
- `추출`  ×1
- `스키마`  ×1
- `대조`  ×1
- `검증`  ×1

## XP 산식 (참고)

```
XP = task×100 + ingest×200 + skill×500 + lint×300 + (tokens / 1000)
Level = floor(sqrt(XP) / 4)
```

토큰·시간을 정확히 반영하려면 `memory/log.md` 항목 본문에 `tokens: N` / `sec: T` 메타를 한 줄 적어두면 자동 합산됩니다.
