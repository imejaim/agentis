---
name: memory-lint
inputs: agentis/agent.md + agentis/memory/**/*.md
outputs: 콘솔 보고서 / (--report) 보고서 파일 / (--fix) 깨진 링크 주석화
script: memory-lint.py
created: 2026-05-26
updated: 2026-05-26
---

# 메모리 lint

위키가 두꺼워질수록 잡음도 늘어난다. lint 는 두뇌의 *정비공* — 깨진 링크, 고아 페이지, 중복/유사 페이지를 결정론으로 잡아낸다.

## 무엇을 검사하나

1. **깨진 위키링크** — `[[X]]` 가 가리키는 페이지가 없을 때. (가장 자주 잡힘 — 페이지 이름 바뀐 뒤 링크 안 고친 경우.)
2. **고아 페이지** — 어디서도 들어오는 링크가 없는 페이지. 코어 페이지(`agent`, `_index`, `overview`, `log`, `hot`, `stats`) 와 인덱스류는 제외.
3. **중복/유사 페이지** — Jaccard 유사도 ≥ 0.80 인 페어. (제목·H1 만 다르고 본문이 사실상 같은 케이스.)

## 절차

1. **현황 확인**:
   ```
   python agentis/workflows/memory-lint.py
   ```
   - 콘솔에 보고서 출력. 안전 — 파일 안 건드림.

2. **보고서 저장** (사용자에게 길게 보여줄 때):
   ```
   python agentis/workflows/memory-lint.py --report memory-lint-2026-05-26.md
   ```

3. **안전한 자동 수정**:
   ```
   python agentis/workflows/memory-lint.py --fix
   ```
   - **깨진 링크만** 자동 처리: `[[X]]` → `<!-- TODO: 깨진 링크 [[X]] -->` (원본 텍스트 보존, 그래프에서만 빠짐).
   - 고아 페이지·중복 페이지는 **자동 삭제 X** — 사용자 결정 필요. 보고서로만.

4. **사람 결정 (수동 정리)**:
   - 깨진 링크 — 페이지 이름 변경이면 링크 텍스트만 고침. 페이지 삭제됐다면 주석 그대로 유지(역사 기록).
   - 고아 페이지 — 정말 안 쓰는 페이지면 `_index.md` 에서 내리고 페이지에 `tags: [archived]` 추가. 삭제는 신중히.
   - 중복 페이지 — 두 페이지 중 더 잘 정리된 쪽을 *기준*으로, 다른 쪽 내용을 머지해서 기준 페이지로 흡수. 흡수된 쪽은 `_index` 에서 내리고 frontmatter 에 `merged_into: [[기준페이지]]` 메모.

5. **로그 갱신**:
   - `memory/log.md` 에 한 줄: `## [날짜] lint | 깨진 N / 고아 M / 중복 K → 처리 X건`.
   - 그래프 갱신: `python agentis/graph/build_graph.py`.

## 임계값 조정

```
python agentis/workflows/memory-lint.py --sim 0.70   # 더 보수적으로 중복 잡기
```

## 주의 / 엣지 케이스

- **`--fix` 는 깨진 링크 한정**. 같은 페이지에서 같은 깨진 대상이 여러 번 나오면 모두 처리.
- **중복 후보 점수가 높아도 의미가 다를 수 있다.** 예: 한 페이지가 다른 페이지의 *요약*이라면 토큰 집합은 비슷해도 의도는 다름 — 머지 X.
- **고아인데 의도된 경우** — `archive/` 같은 별도 폴더의 페이지, 또는 사용자만 직접 읽는 색인 페이지. 코어 stems 외엔 다 잡히므로, 의도된 고아는 frontmatter 에 `tags: [orphan-ok]` 추가하면 다음 lint 때 사용자가 알아보기 쉬움(스크립트가 자동 무시하진 않음 — 정직 보고가 우선).
- **`_brain/` 폴더는 lint 대상에서 제외됨** — build_brain_index.py 와 같은 가드.

## 함께 돌리기 — 정기 정비 루틴

분기에 한 번, 또는 메모리 페이지가 50개 넘어갈 때 권장:

```
python agentis/workflows/memory-lint.py --report lint-yyyy-mm-dd.md
# (사람 검토)
python agentis/workflows/memory-lint.py --fix
python agentis/workflows/skill-도태.py --apply
python agentis/memory/_brain/build_brain_index.py
python agentis/graph/build_graph.py
```

## 관련

- 씨드 §3-7 자가 도태·lint
- 메모리: `memory/_brain/README.md`, `memory/_brain/holonomic.md`
- 함께: [skill-도태](skill-도태.workflow.md) — 안 쓰는 스킬 보관
