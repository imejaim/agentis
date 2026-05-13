# 규격이 브랜치 — 2026-05-14

이 폴더는 `규격이` 에이전트의 **브랜치 스냅샷**입니다. (Agentis: 씨드 → 브랜치 → 메인)

## 출처

- 원본 에이전트: **규격이**
- 원본 사용자: `홍길동 (품질팀)` → 브랜치에서는 `[REDACTED]` 로 치환됨
- 브랜치 생성일: 2026-05-14

## 포함 / 제외 통계

**fork/** (통째로 받기용 — 정체성 + 두뇌 + 역량)
- 포함 파일: 26
- 자동 제외: `share: private` 0 / 사용자 본인 엔티티 1
- 사용자 지정 제외: 0

**pack/** (역량만 받기용)
- skills: 2 / workflows: 10 / concepts: 3

## 씨드(seed)
- 씨드 사본 동봉됨 (`_seed/agentis.md` — 원본: `.clinerules`). 받는 분이 그대로 `.clinerules` 로 쓰면 됨.

## ⚠ 의심 누출 경고 (사람 검토 권장)
- fork/memory\_index.md 에 사용자 이름('홍길동') 흔적이 있어요.
- fork/memory\hot.md 에 사용자 이름('홍길동') 흔적이 있어요.
- fork/memory\log.md 에 사용자 이름('홍길동') 흔적이 있어요.
- fork/memory\overview.md 에 사용자 이름('홍길동') 흔적이 있어요.
- fork/memory\sources\2026-05-08-시험성적서-모델X.md 에 사용자 이름('홍길동') 흔적이 있어요.
- fork/memory\concepts\kc-rohs-기초.md 가 소스 페이지 [[sources/2026-05-10-제출문서목록-v2]] 를 가리켜요 (소스가 같이 포함됐다면 OK, 아니면 깨진 링크).
- fork/memory\concepts\체크리스트-대조-원칙.md 가 소스 페이지 [[sources/2026-05-10-제출문서목록-v2]] 를 가리켜요 (소스가 같이 포함됐다면 OK, 아니면 깨진 링크).
- fork/memory\entities\kc-안전인증.md 가 소스 페이지 [[sources/2026-05-10-제출문서목록-v2]] 를 가리켜요 (소스가 같이 포함됐다면 OK, 아니면 깨진 링크).
- fork/memory\entities\시험성적서.md 가 소스 페이지 [[sources/2026-05-08-시험성적서-모델X]] 를 가리켜요 (소스가 같이 포함됐다면 OK, 아니면 깨진 링크).

> 위 경고는 자동 스크럽이 완전하지 않을 수 있다는 신호입니다. fork/agent.md 와 fork/memory/concepts·entities 의 해당 파일을 한 번 훑어보고 필요하면 손으로 수정하세요.

## 받는 사람 안내
이 폴더를 작업 폴더에 두고 Cline 에 **`안녕`** 한 마디만 하면 됩니다. 씨드(`.clinerules`)가:
- 받는 분 작업 폴더에 **`agentis/` 가 없다면** → `fork/` 를 새 `agentis/` 로 복사하고 **리브랜드 미니 인터뷰** 진행
- 받는 분 작업 폴더에 **이미 `agentis/` 가 있다면** → `pack/` 만 합치는 **팩 모드** 진행

씨드가 작업 폴더에 아직 없다면 `_seed/agentis.md` 를 `.clinerules` 로 넣으세요. (또는 https://github.com/imejaim/agentis 에서 받기)