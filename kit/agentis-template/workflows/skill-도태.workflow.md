---
name: skill-도태
inputs: agentis/skills/ + agentis/memory/log.md
outputs: 콘솔 보고 / (--apply 시) skills/_attic/<이름>__retired-YYYY-MM-DD/
script: skill-도태.py
created: 2026-05-26
updated: 2026-05-26
---

# 자가 도태 (씨드 §3-7)

30일+ 안 쓰인 스킬을 `skills/_attic/` 으로 이동(보관). **삭제하지 않음** — 사용자가 다시 꺼내쓸 수 있게 항상 옆에 둔다.

## 동기

스킬이 누적되면 `memory/_brain/build_brain_index.py` 의 결과에 잡음이 늘고, `[[skills/...]]` 링크가 그래프에서 *죽은 가지*처럼 남는다. 자가 도태는 두뇌가 *자신을 가지치기*하는 절차.

## 절차

1. **현황 확인** (dry-run, 변경 X):
   ```
   python agentis/workflows/skill-도태.py
   ```
   - 출력: 각 스킬의 마지막 사용일 + 도태 후보 표.
   - 사용 횟수는 `memory/log.md` 에서 다음 패턴으로 카운트:
     - `## [날짜] task | ... uses: <스킬>` (권장 — `uses:` 메타)
     - `[[skills/<이름>]]` 링크가 본문에 나오는 것도 사용으로 침 (구버전 호환).

2. **사람 결정** — 보고서를 사용자에게 보여주고 다음 케이스 확인:
   - 정말 안 쓰는 스킬인가? (계절성·연 1회만 쓰는 것도 있음)
   - 안 쓰는 이유가 *스킬이 별로*여서인가, *지금 일이 없어서*인가?

3. **적용**:
   ```
   python agentis/workflows/skill-도태.py --apply
   ```
   - `skills/<이름>/` 이 `skills/_attic/<이름>__retired-YYYY-MM-DD/` 로 이동.
   - `memory/log.md` 에 `## [날짜] lint | 자가 도태 — N개 스킬 _attic/ 으로 보관` 한 줄.
   - 그래프 갱신: `python agentis/graph/build_graph.py` — `_attic/` 은 그래프 빌더가 인식하지 않으므로 자동으로 노드가 사라짐.

4. **복구** (필요 시):
   - 단순히 `_attic/<이름>__retired-...` 를 다시 `skills/<이름>` 으로 이동하면 끝.
   - 복구하면 `memory/log.md` 에 `## [날짜] skill | <이름> 복구 — 사용 재개` 한 줄 적기.

## 임계 일수 조정

기본 30일. 더 보수적으로 60일로 두려면:
```
python agentis/workflows/skill-도태.py --days 60
```

## 주의 / 엣지 케이스

- **첫 운영(로그 짧을 때)** — 모든 스킬이 "사용 기록 없음" 으로 잡힘 → `--apply` 하면 다 _attic 으로 가버린다. 도태 전에 사용자에게 한 번 더 묻기 ("정말 다 안 쓰셨어요?").
- **`_attic/` 도 그래프에서 빠진다** — `build_graph.py` 의 collect 로직이 `skills/<dir>/SKILL.md` 만 본다. `_attic` 은 _ 접두라 자동 제외. 의도된 동작.
- **스킬 안의 결정론 .py 는 보존된다** — 도태는 폴더째 이동이므로 코드·문서 다 살아있다. 두뇌의 *비활성 영역*으로 보내는 것.

## 관련

- 씨드 §3-7 자가 도태
- 메모리: `memory/_brain/README.md`, [[memory/log]]
- 함께: [memory-lint](memory-lint.workflow.md) — 깨진 링크·고아 페이지 정리
