# workflows/ — 업무 워크플로우

워크플로우 = 한 가지 업무를 처음부터 끝까지 어떻게 처리하는지 적은 절차서. 스킬보다 가볍게 시작할 수 있고, 굳어지면 스킬로 승격시키기도 합니다.

중요: 이 `agentis/workflows/` 폴더는 에이전트 내부 작업장입니다. **Cline 하단 Workflows 탭이 직접 읽는 업무 규칙은 작업 폴더의 `.clinerules/workflows/` 에도 있어야 합니다.** 확정된 주요 업무·반복 업무는 여기서 작성한 `<업무>.workflow.md` 를 `.clinerules/workflows/<업무>.md` 로 동기화해 Cline 하네스가 매번 따르게 합니다.

핵심 원칙(커널과 동일): **가능한 단계는 Python 코드로** 처리하고(`*.py`), 코드는 입력/출력 경로를 인자로 받게 짜고, **검증 단계를 반드시 포함**합니다. (사내 도구 — 재실행·재현·검증 가능해야 함.)

## 구조

```
workflows/
  README.md
  _template.workflow.md     ← 새 워크플로우 만들 때 이걸 복사
  <업무이름>.workflow.md     ← 절차서
  <업무이름>.py             ← (있으면) 그 업무의 결정론적 처리 스크립트
```

## 쓰는 법

1. 새 업무가 들어오면 `_template.workflow.md` 를 복사해 `<업무이름>.workflow.md` 로.
2. 절차를 적되, "이건 코드로 할 수 있다" 싶은 단계는 `<업무이름>.py` 에 구현.
3. 실행: `python agentis/workflows/<업무이름>.py --in <입력경로> --out <출력경로>` → 산출물 + 검증결과 확인.
4. 확정 업무가 되었으면 `.clinerules/workflows/<업무>.md` 로 복사/동기화한다. 이 위치가 Cline Workflows 탭의 룰 배포 위치다.
5. 끝나면 씨드 §3-8 의 마감 루프를 따른다: 정리 후보 보고, 검증 실행, `memory/log.md`/`hot.md` 갱신, `graph.html`/`flow.html`/`stats.md` 갱신, Git 상태 확인, 사용자 보고.
6. 같은 업무가 또 오면 → `.clinerules/workflows/` 의 룰을 먼저 따른다. 굳어졌으면 사용자에게 "스킬로 올릴까요?" 제안.

## 기본 동봉 워크플로우 (공유와 진화 — §5 in seed)

| 파일 | 무엇 |
|---|---|
| [브랜치-내보내기](브랜치-내보내기.workflow.md) + `.py` | 이 에이전트를 다른 사용자에게 넘길 브랜치 폴더로 묶기 (자동 제외: 사용자 본인 정보 / 본인 엔티티 / `share:private`) |
| [팩-병합](팩-병합.workflow.md) + `.py` | 다른 사람 브랜치의 pack 만 내 에이전트에 합치기 (agent.md·sources·log·hot·entities·overview·_index 안 건드림) |
| [브랜치-비교](브랜치-비교.workflow.md) + `.py` | 두 에이전트/브랜치의 스킬·워크플로우·개념 디프 보고서 (메인 큐레이션용) |
| [메인-동기화](메인-동기화.workflow.md) + `.py` | `agent.md` 의 `main_repo:` 가 설정된 경우, 사내 메인 레포와 pull/push-prep/check |
| [memory-lint](memory-lint.workflow.md) + `.py` | 두뇌 위키의 깨진 링크·고아 페이지·중복 후보 점검 |
| [skill-도태](skill-도태.workflow.md) + `.py` | 오래 안 쓴 스킬을 삭제하지 않고 `_attic/` 보관 후보로 관리 |
| [프로젝트-정리](프로젝트-정리.workflow.md) + `.py` | 프로젝트 중복/임시/생성물 후보를 보고하고 `_archive/` 로 보관 이동 |
