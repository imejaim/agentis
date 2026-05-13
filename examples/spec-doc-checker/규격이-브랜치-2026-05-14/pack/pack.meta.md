---
type: pack-meta
origin: 규격이
branch_date: 2026-05-14
created: 2026-05-14
---

# 규격이 팩 (역량만)

`규격이` 에서 추출한 **역량 슬라이스**입니다. 받는 사람의 기존 에이전트에 합치는 용도(§5-3 팩 모드).

## 포함
- skills/         — 2 파일 (스킬 폴더들)
- workflows/      — 10 파일 (워크플로우 + 결정론 .py)
- memory/concepts/ — 3 파일 (도메인 일반 개념. share=private 인 것은 제외)

## 포함되지 않은 것 (의도)
- `agent.md` — 정체성은 받는 쪽 것을 유지
- `memory/sources/`, `memory/entities/`, `memory/log.md`, `memory/hot.md`, `memory/overview.md`, `memory/_index.md` — 받는 쪽 데이터 그대로 둠
- `graph/` — 받는 쪽 빌더가 새 메모리에 맞춰 다시 그림

## 합치는 법
받는 사람 작업 폴더에서:
```
python agentis/workflows/팩-병합.py --pack <이 팩 폴더 경로> --strategy plan-only   # 충돌 미리보기
python agentis/workflows/팩-병합.py --pack <이 팩 폴더 경로> --strategy <결정>      # 결정 반영해 실제 머지
```
