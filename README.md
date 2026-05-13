# Agentis

> 사내 **VS Code + cline SR** 환경에서, **워크스페이스 룰 파일 하나**로 부팅되는 **업무처리 에이전트 키트**.
> 카오스 → 유니버스. 쓰는 사람도 크고, 에이전트도 큰다.

## 이게 뭔가요

Agentis는 "에이전트를 만드는 에이전트 환경"입니다. 동료가 자기 작업 폴더에 이 키트를 복붙하고 클라인에게 **"안녕"** 한 마디만 하면:

1. 에이전트가 **이름을 지어달라**고 합니다.
2. 짧은 **clarify 인터뷰**로 "무슨 업무를 도울지" 함께 정합니다.
3. **사용법을 안내**하고, 자기 **정체성·기억(brain)** 구조를 스스로 만듭니다.
4. 이후 일하면서 배운 것이 **위키 + 지식 그래프**로 쌓이고, 반복되는 일은 **스스로 스킬로** 만들며 진화합니다.
5. 세션이 바뀌어도 **그 프로젝트를 다 기억**합니다.

목적은 코딩 에이전트도 개인 비서도 아닌 **업무처리 에이전트** — 그리고 동료들이 "에이전틱하게 일한다는 게 뭔지" 직접 체험하게 하는 것.

## 빠른 시작 (예정)

```text
경로 A) 이 레포의 kit/ 폴더를 내 작업 폴더에 복붙 → 클라인에게 "이 폴더 보고 기본 셋팅해줘"
경로 B) cline SR 워크스페이스 룰에 seed/ 의 파일 1개만 넣고 → "안녕"
```

> ⚠️ 아직 설계/구현 단계입니다. 자세한 계획은 [`PLAN.md`](./PLAN.md) 참고 (현재 v0.5).

**v1.0 핵심**:
- ⓪ **결정론 우선** — 사내 에이전트라 정확성·신뢰성이 최우선. 업무처리는 최대한 **Python 코드**로 짜서 재실행·검증 가능하게. (md = 지식·규약, py = 실제 처리)
- ① **Cline 룰(md 파일) 기반**으로 동작 — superpowers처럼
- ② **Cline 메모리뱅크 → 살아있는 LLM-위키** — Hermes식 자가확장 + LLM-위키 방식으로 진화시켜 "두뇌"로
- ③ **graphify로 Obsidian처럼 그래프화** → 지식 쌓이는 게 눈에 보이게 (목표 그래프 스타일: [`docs/ref-graph-style.png`](./docs/ref-graph-style.png))

## 레포 구조 (계획)

| 경로 | 내용 |
|---|---|
| `seed/` | The Seed — `.clinerules` 부트스트랩 파일 (이것 하나로 완결) |
| `kit/` | The Kit — 스킬 라이브러리, 메모리 스캐폴드, 워크플로우 템플릿, 그래프 뷰어 |
| `docs/` | 컨셉 설명, 사내 도입 안내, 에이전트 예시 카탈로그 |
| `examples/` | 예제 에이전트 |
| `PLAN.md` | 기획서 (현재 v0.3) |
| `reference/` | 참고용 원본 레포 클론 — **깃이그노어, 커밋 안 함** |

## 영감을 준 것들

- [cline/cline](https://github.com/cline/cline) — 호스트 플랫폼 (cline SR의 베이스)
- [obra/superpowers](https://github.com/obra/superpowers) — 시작 인터뷰의 clarify 흐름
- [nousresearch/hermes-agent](https://github.com/nousresearch/hermes-agent) — 세션 넘는 기억 + 스킬 자가 진화
- [graphify](https://graphify.net/) ([safishamsi/graphify](https://github.com/safishamsi/graphify)) — 지식 그래프 시각화 ("두뇌")
- [Karpathy — LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — LLM이 직접 유지보수하는 지식베이스
- [지식 그래프 실사용기 (brunch)](https://brunch.co.kr/@abrahamsong/164)

## 상태

설계 중. Phase 0(레포·레퍼런스 셋업) 완료 → 다음은 The Seed v1 초안. cline SR 환경 실측은 추후, v1.0은 표준 Cline 가정으로 진행. 진행 상황은 `PLAN.md` 참고.
