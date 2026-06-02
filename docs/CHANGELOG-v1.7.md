# CHANGELOG — v1.6 → v1.7

> 작성: Hermes / 2026-06-02. 새 Cline 세션에서 이미 부팅된 Agentis가 첫 만남 인터뷰를 반복하는 문제를 막기 위한 안정화 릴리스.

## 핵심 변경

### 1. 부팅 완료 sentinel 규약 추가

첫 셋업이 끝난 에이전트는 다음 파일을 만든다.

```yaml
agentis/.bootstrapped
```

내용 예:

```yaml
bootstrapped: true
bootstrapped_at: YYYY-MM-DD
seed_version: 1.7
agent_name: <에이전트 이름>
state: operational
```

이 파일은 `.clinerules/agentis.md` 가 새 세션마다 다시 로드되더라도 §1 첫 만남 인터뷰로 되돌아가지 않게 하는 상태 신호다.

### 2. §0 부팅 상태 판정 강화

다음 중 하나라도 참이면 이미 운영 중으로 본다.

- `agentis/.bootstrapped` 존재
- `agentis/agent.md` 가 있고 템플릿 placeholder가 대부분 채워져 있음
- `agentis/memory/log.md` 에 `setup |` 항목 존재

운영 중이면 이름·목적·주요 업무를 다시 묻지 않고 §0-2 평소 세션으로 들어간다.

### 3. 상태 확인 요청 처리 명시

다음 요청은 초기 인터뷰 트리거가 아니라 상태 요약 요청으로 처리한다.

- `안녕`
- `뭐 했지?`
- `지금까지 한 것 정리해줘`
- `앞으로 할 일 알려줘`
- `현재 상태 알려줘`
- `어디까지 했지?`
- `다음 액션 정리해줘`

기본 응답 형식:

- 지금까지 한 일
- 현재 진행 중
- 열린 쟁점
- 다음 할 일

근거 파일:

- `agentis/agent.md`
- `agentis/memory/hot.md`
- `agentis/memory/log.md`
- 필요 시 `agentis/memory/overview.md`

## 변경 파일

- `.clinerules/agentis.md`
- `seed/agentis.md`
- `docs/agentis-view.html`
- `kit/agentis-template/agent.template.md`
- `README.md`
- `docs/CHANGELOG-v1.7.md`

## 기대 효과

부팅 완료 후 새 Cline 세션에서 사용자가 단순히 상태를 물어도, Agentis가 처음 만난 것처럼 이름·목적 인터뷰를 반복하지 않고 기존 기억을 읽어 이어서 답한다.
