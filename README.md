# 사람이 쓴 글

clineSR 창에 여기 깃허브 주소 넣고, '이 주소 보고 셋팅해줘' 요렇게 하세요.

# AI 가 쓴 글

# Agentis

**Agentis v1.10** — 사내 **VS Code + cline SR** 환경에서, **워크스페이스 룰 파일 하나**로 부팅되는 **업무처리 에이전트 키트**.

> 카오스 → 유니버스. 쓰는 사람도 크고, 에이전트도 큰다.
> v1.10 핵심: 루트 `workflows.html` / `holonomic-brain.html`, `.clinerules/workflows` 결정론 렌더, 안전 업그레이드 보강.

## v1.9.1 핵심 구조 — Rules는 라우팅, Workflows는 확정 업무

사내 Cline 적용 결과, 확정 업무 흐름을 `agentis/workflows/` 내부에만 두면 Cline 하단 **Workflows** 탭/하네스가 엄격히 따르지 않을 수 있습니다. 그래서 Agentis의 기준 구조를 아래처럼 정리했습니다.

```text
.clinerules/
  agentis.md              # 공통 커널: 기억, 검증, 완료 루프
  10-agent-routing.md     # 자연어 요청 → workflow 라우터
  workflows/              # Cline Workflows 탭용 확정 업무 규칙
    00-전체업무순서.md     # 오케스트레이터
    <업무>.md

agentis/
  workflows/              # 내부 초안·스크립트·진화 후보
```

원칙은 간단합니다.

- **Rules**: 항상 알아야 하는 운영 원칙과 라우팅만 둔다.
- **Workflows**: 확정 업무 순서와 기능별 절차를 둔다.
- **agentis/workflows**: 에이전트가 만드는 초안/스크립트 작업장이다.
- 반복/확정 업무는 `agentis/workflows/` 에서 끝내지 말고 `.clinerules/workflows/` 로 동기화한다.

자세한 구조 설명: [`docs/cline-rules-workflows-structure.md`](./docs/cline-rules-workflows-structure.md)

## v1.10 루트 사람용 보기 — workflows.html / holonomic-brain.html

사람에게 보여주는 안내판은 `agentis/` 내부가 아니라 **작업 폴더 루트**에 생성합니다.

```text
<작업폴더>/workflows.html          # .clinerules/workflows/*.md 결정론 업무 지도
<작업폴더>/holonomic-brain.html    # agentis/memory/ 기반 사람용 두뇌 지도
<작업폴더>/holonomic-brain.json    # 두뇌 지도 데이터
agentis/graph/graph.html           # 기존 3D 호환 뷰 유지
agentis/graph/flow.html            # 기존 primary_tasks 스윔레인 유지
```

자동 갱신 명령:

```bash
python agentis/graph/refresh_views.py --workspace .
```

`workflows.html`의 정본 입력은 `.clinerules/workflows/` 입니다. 확정 업무가 추가되거나 바뀌면 markdown을 고친 뒤 위 refresh 명령으로 HTML을 다시 만듭니다. 생성 HTML은 편집 정본이 아니므로, 기존 사용자의 기억·스킬·씨드를 지우지 않습니다.

## 잠깐 — 만들지 마세요

Cline 을 "코딩 에이전트"로만 알고 계셨다면, 업무 자동화 에이전트를 쓰려고 이런 걸 만들려 하실 수 있습니다:

- ❌ 백엔드 API 서버 (FastAPI / Express) + LLM 호출 래퍼
- ❌ 채팅 서비스 UI (React + WebSocket)
- ❌ 에이전트 SDK + 자체 호스팅
- ❌ Docker / 클라우드 배포

**전부 필요 없습니다.** 배보다 배꼽이 커집니다.

VS Code + Cline (사내 cline SR) 이 이미 에이전트 호스트입니다.
이 레포의 **씨드(`seed/agentis.md`) 한 파일**을 작업 폴더의 `.clinerules/agentis.md` 로 복붙하고 "안녕" 만 하면, 그게 당신의 업무처리 에이전트가 깨어나는 순간입니다.

## 3분 셋업 (정말로)

1. 작업 폴더에 `.clinerules/` 폴더 만들기 (이미 있으면 패스)
2. 이 레포의 `seed/agentis.md` 내용을 `.clinerules/agentis.md` 로 그대로 복사
3. 이 레포의 `seed/10-agent-routing.md` 를 `.clinerules/10-agent-routing.md` 로 복사 — 자연어 요청을 workflow로 연결하는 라우터입니다.
4. 이 레포의 `kit/agentis-template/workflows/*.workflow.md` 를 `.clinerules/workflows/*.md` 로 복사 — Cline 하단 **Workflows** 탭이 읽는 업무별 규칙입니다.
5. 더 갖춰서 시작하려면 `kit/agentis-template/` 폴더를 작업 폴더에 `agentis/` 라는 이름으로 통째로 복사 (선택)
6. Cline 대화창에 **`안녕`**

끝. 이제 에이전트가 자기 이름을 짓고, 짧은 인터뷰 후 (원하면 딥인터뷰), 사용법을 안내합니다.

## 사내 동료 설치 (가장 안전한 방법)

위 3분 셋업을 cline 한 명에게 시키면, 환경에 따라 `.clinerules/` 가 안 생기거나 의도치 않은 다른 작업까지 같이 하는 경우가 있습니다. **결정론 인스톨러**(`install.py`)는 정확히 두 가지 — 룰 파일 복사 + (선택) 키트 복사 — 만 합니다. **git push 도 네트워크 요청도 하지 않습니다.**

### A) 더블클릭 (가장 단순)
1. 이 레포(`agent_seed`) 를 사내 깃에서 다운로드
   ```
   git clone https://github.sec.samsung.net/dongho-yoon/agent_seed
   ```
2. 압축 풀린 `agent_seed/` 폴더 안에서 **`install.bat`** (Windows) 또는 **`install.sh`** (Mac/Linux) 더블클릭
3. 안내에 따라 **작업 폴더 절대 경로** 한 번만 입력
4. VS Code 에서 그 폴더 열고 cline 에 "안녕"

### B) cline 에게 시키기
cline 대화창에 정확히 다음만 입력 (다른 작업은 시키지 마세요):

> 이 폴더의 `install.py` 를 `--target "<내 작업 폴더 절대 경로>"` 와 함께 실행해줘. 그 외 다른 작업은 하지 마.

### C) 직접 명령
```
cd agent_seed
python install.py --target "C:\내작업\프로젝트A"
```

설치되는 것은 정확히 네 가지:
- `<작업폴더>/.clinerules/agentis.md` (워크스페이스 룰)
- `<작업폴더>/.clinerules/10-agent-routing.md` (자연어 요청 → workflow 라우팅 룰)
- `<작업폴더>/.clinerules/workflows/` (Cline Workflows 탭용 업무별 룰)
- `<작업폴더>/agentis/` (검증된 키트, 선택 — `--no-kit` 로 끌 수 있음)

자주 쓰는 옵션:
- `--here` : 현재 디렉토리에 설치 (`--target` 와 상호배타)
- `--dry-run` : 변경 없이 무엇이 만들어질지 보고만
- `--force` : 이미 설치되어 있으면 백업 후 룰 파일 덮어쓰기 (`agentis/` 생성물은 기본 보존)
- `--upgrade-kit` : 기존 `agentis/` 에 새 키트를 **안전 병합**. 기존 `.clinerules/agentis.md` 와 `.clinerules/workflows/` 사용자 수정본은 보존하고, `memory/`, `skills/`, `agent.md`, `graph/graph.html`, `graph/flow.html`, `graph/graph.json`, `workflows.html`, `holonomic-brain.html` 은 덮어쓰지 않습니다. `# agentis-kit:` 마커가 있는 표준 스크립트만 백업 후 갱신합니다.
- `--no-kit` : 룰만 설치, 키트는 건너뜀
- `--quiet` : 출력 최소화

설치기는 **git push 를 하지 않고** **네트워크 요청도 하지 않습니다**. 작업 폴더 안에서만 동작합니다.

## 이게 뭔가요

Agentis는 "에이전트를 만드는 에이전트 환경"입니다. 동료가 자기 작업 폴더에 씨앗 파일 하나 넣고 클라인에게 **"안녕"** 한 마디만 하면:

1. 에이전트가 **이름을 지어달라**고 합니다.
2. 짧은 **clarify 인터뷰**로 "무슨 업무를 도울지" 함께 정하고, 설계 요약을 보여주고 승인받습니다.
3. 자기 **정체성·기억(brain)** 구조(`agentis/`)를 스스로 만들고 **사용법을 안내**합니다.
4. 이후 일하면서 — 가능한 건 **Python 코드로 짜서 검증**하고(정확성·신뢰성 우선), 배운 것이 **위키 + 지식 그래프**로 쌓이고, 반복되는 일은 **스스로 스킬로** 만들며 진화합니다.
5. 업무가 끝나면 그냥 산출물만 던지고 끝내지 않고, **정리 → 검증 → 기억 갱신 → graph/flow/stats 갱신 → Git 관리 → 사용자 보고**까지 마감 루프를 돕습니다. 필요 없는 파일은 삭제하지 않고 `_archive/` 보관 후보로 보고합니다.
6. 세션이 바뀌어도 **그 프로젝트를 다 기억**합니다. 이미 셋업된 에이전트는 `agentis/.bootstrapped` 와 `agentis/agent.md` 를 보고 이어서 동작하므로, 새 세션에서 "안녕" 또는 "지금까지 뭐 했지?"라고 해도 첫 인터뷰를 다시 시작하지 않습니다.

목적은 코딩 에이전트도 개인 비서도 아닌 **업무처리 에이전트** — 그리고 동료들이 "에이전틱하게 일한다는 게 뭔지" 직접 체험하게 하는 것.

## 써보기

**A. 가장 간단히 (씨앗만)**
1. cline SR 쓸 작업 폴더에 `.clinerules` 파일을 만들고 [`seed/agentis.md`](./seed/agentis.md) 내용을 그대로 붙여넣기. (또는 `.clinerules/agentis.md` 로 저장)
2. Cline 대화창에 **`안녕`**.
3. 인터뷰 → 승인 → 에이전트가 `agentis/` 폴더(정체성·메모리·스킬·워크플로우·그래프)를 스스로 생성 → 사용법 안내 → 첫 업무.
4. 일 시키고, 끝나면 `python agentis/graph/build_graph.py --open` 으로 두뇌 그래프 보기. 세션 닫았다 다시 열어도 다 기억함.

**B. 더 갖춰서 (키트까지)**
1. [`kit/agentis-template/`](./kit/agentis-template/) 폴더를 작업 폴더에 **`agentis/`** 라는 이름으로 통째로 복사.
2. 위 A의 1~2번 동일. 에이전트가 빈 템플릿을 인터뷰 결과로 채움.

**C. 먼저 구경 (예제)**
- [`examples/spec-doc-checker/`](./examples/spec-doc-checker/) — 규격인증 문서 자동화 에이전트 "규격이"가 며칠 일한 모습.
  ```bash
  cd examples/spec-doc-checker
  python agentis/graph/build_graph.py --open      # 두뇌 그래프 (브라우저로 열림)
  python agentis/skills/checklist-대조/run.py --checklist agentis/sample-data/요구체크리스트.txt --submitted agentis/sample-data/제출문서목록.txt --out agentis/sample-data/대조결과.md
  python agentis/workflows/시험성적서-항목추출.py --in agentis/sample-data/시험성적서-모델X.txt --out agentis/sample-data/항목표.csv
  ```
  > 자세한 설치는 [`seed/README.md`](./seed/README.md), 키트 설명은 [`kit/README.md`](./kit/README.md), 계획은 [`PLAN.md`](./PLAN.md) (현재 v0.6).

## v1.0 핵심

- ⓪ **결정론 우선** — 사내 에이전트라 정확성·신뢰성이 최우선. 업무처리는 최대한 **Python 코드**로 짜서 재실행·검증 가능하게. (md = 지식·규약, py = 실제 처리)
- ① **Cline 룰(md 파일) 기반**으로 동작 — superpowers처럼, 빌드·설치 의존 없음
- ② **Cline 메모리뱅크 → 살아있는 LLM-위키** — Hermes식 자가확장 + LLM-위키 방식으로 진화시켜 "두뇌"로 (`agentis/memory/`)
- ③ **3D 두뇌 그래프 (v1.4)** → 지식 쌓이는 게 눈에 보이게. `agentis/graph/build_graph.py` 가 Three.js + 3d-force-graph 인라인 자체완결 `graph.html` 생성 (외부 의존 0 — 사내망/오프라인 OK). VS Code 의 Simple Browser 로 사이드 탭에 띄움. graphify 본체 연동은 추후. (목표 스타일: [`docs/ref-graph-style.png`](./docs/ref-graph-style.png))

## v1.9 운영 보강

- **기본 이름: 라대리** — 사용자가 바꾸면 그 이름을 정본으로 사용합니다.
- **Cline 진입점 강화** — Cline이 반드시 읽는 `.clinerules/agentis.md` 안에 정리·검증·기억·보고·Git 관리 규칙을 직접 넣고, `.clinerules/10-agent-routing.md` 는 자연어 요청을 workflow로 라우팅하며, Cline 하단 Workflows 탭이 읽는 `.clinerules/workflows/` 에 업무별 절차서를 함께 배포합니다.
- **완료 마감 루프** — 업무 완료 시 `정리 → 검증 → 기억 갱신 → graph/flow/stats 갱신 → Git 관리 → 사용자 보고`를 기본 흐름으로 둡니다.
- **정리 프로세스** — `agentis/workflows/프로젝트-정리.py` 가 중복/임시/생성물 후보를 보고하고, 적용 시에도 삭제가 아니라 `_archive/` 로 보관 이동합니다.
- **검증 프로세스** — 만든 산출물에 맞는 실제 검증 명령을 돌리고, 실패/미검증은 그대로 보고합니다.
- **안전 업그레이드** — 1.7/1.8 프로젝트에 1.9 키트를 올릴 때 `memory/`, `agent.md`, `graph.html`, `flow.html` 을 덮지 않습니다. 새 기능은 `--upgrade-kit` 으로 표준 스크립트만 백업 후 병합합니다.
- **flow.html 재정의** — 업무 히스토리가 아니라 프로젝트의 주요 업무 3~5개와 각 업무의 표준 워크플로우를 스윔레인으로 보여줍니다.

## 레포 구조

| 경로 | 내용 |
|---|---|
| `seed/agentis.md` | The Seed — `.clinerules/agentis.md` 로 넣는 부트스트랩 커널 |
| `seed/10-agent-routing.md` | 자연어 요청을 `.clinerules/workflows/` 의 업무별 workflow로 연결하는 라우팅 룰 |
| `seed/README.md` | 씨앗 설치 가이드 |
| `kit/agentis-template/` | 작업 폴더에 `agentis/` 로 복사하는 템플릿 (agent 템플릿 / memory 스캐폴드+운영규약 / skills·workflows 포맷 / `build_graph.py`) |
| `kit/agentis-template/workflows/00-전체업무순서.workflow.md` | 전체 업무 오케스트레이터 workflow 템플릿 |
| `kit/README.md` | 키트 사용법 |
| `examples/spec-doc-checker/` | 예제 에이전트 "규격이" — 채워진 `agentis/` + 동작하는 `run.py` 2종 + 샘플 데이터 |
| `docs/` | `ref-graph-style.png` (목표 그래프 스타일). 컨셉·도입 문서는 추후 |
| `PLAN.md` | 기획서 (v0.6) |
| `reference/` | 참고용 원본 레포 클론 — **깃이그노어, 커밋 안 함** |

## 영감을 준 것들

- [cline/cline](https://github.com/cline/cline) — 호스트 플랫폼 (cline SR의 베이스)
- [obra/superpowers](https://github.com/obra/superpowers) — 시작 인터뷰의 clarify 흐름, "md = 워크플로우" 구조
- [nousresearch/hermes-agent](https://github.com/nousresearch/hermes-agent) — 세션 넘는 기억 + 스킬 자가 진화
- [graphify](https://graphify.net/) ([safishamsi/graphify](https://github.com/safishamsi/graphify)) — 지식 그래프 시각화 ("두뇌")
- [Karpathy — LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — LLM이 직접 유지보수하는 지식베이스
- [지식 그래프 실사용기 (brunch)](https://brunch.co.kr/@abrahamsong/164)

## 공유 = 브랜치 (패키지) 만들기

성장한 에이전트를 동료에게 넘기려면 **API 배포 X**, **브랜치(패키지) 파일 전달 ✅** 입니다.

- 사용자가 "내 에이전트 다른 동료에게 넘기고 싶어"라고 하면 에이전트가 직접 `agentis/workflows/브랜치-내보내기.py` 를 돌려 zip 한 폴더를 만듭니다.
- 동료는 그 폴더를 자기 작업 폴더 옆에 놓고 Cline 에게 `안녕` → 자동으로 리브랜드 모드로 받습니다.
- 사내 깃 (GitHub Enterprise / GitLab / Gitea / 단순 폴더 미러) 가 있으면 `agent.md` 의 `main_repo:` 필드에 URL 박고, 에이전트 레벨이 5 이상일 때 자동 푸시 옵션도 활성화됩니다 (자세한 건 §5).

자세한 흐름과 명령어는 아래 "에이전트 공유 — 씨드 → 브랜치 → 메인" 섹션을, 사내 깃 배포 전략은 [`docs/배포-사내깃허브.md`](./docs/배포-사내깃허브.md) 를 참고하세요.

## 에이전트 공유 — 씨드 → 브랜치 → 메인

잘 키운 에이전트를 동료에게 넘기거나, 사내 메인으로 표준화하는 방법. (Git 메타포 그대로.)

- **씨드(seed)** — 모든 에이전트의 출발점. `seed/agentis.md` 한 파일.
- **브랜치(branch)** — 진화된 에이전트의 송신용 사본. 자동으로 ① 사용자 본인 식별 정보 ② 본인의 사용자 엔티티 페이지 ③ `share: private` 태그된 페이지를 빼고 묶어줌. 사용자가 추가로 빼고 싶은 것은 짧은 인터뷰로 확인.
- **메인(main)** — `agent.md` 에 `main_repo:` (사내 깃 레포 URL) 가 설정되었을 때만 활성화. 사내 표준 에이전트. pull/push-prep/check 가능.

만들고 받는 법:

```bash
# (A) 잘 키운 에이전트를 가진 사람: 에이전트에게 "브랜치 만들어줘" → 내부적으로:
python agentis/workflows/브랜치-내보내기.py
# → 작업폴더 옆에 <에이전트이름>-브랜치-YYYY-MM-DD/ 폴더 생성 (BRANCH.md + _seed/ + fork/ + pack/)

# (B) 처음 받는 사람: 그 폴더를 자기 작업 폴더에 두고 Cline 대화창에 "안녕"
# → 씨드가 자동 감지 → 리브랜드 미니 인터뷰 (이름·환경 다듬기)

# (B') 이미 자기 에이전트가 있고 역량만 가져오고 싶은 사람:
python agentis/workflows/팩-병합.py --pack <받은폴더>/pack --strategy plan-only   # 충돌 미리보기
python agentis/workflows/팩-병합.py --pack <받은폴더>/pack --strategy rename-incoming  # 결정 반영

# (관리자) 여러 사람 브랜치 비교 → 메인 큐레이션:
python agentis/workflows/브랜치-비교.py <A 브랜치> <B 브랜치> --out 비교결과.md
```

용어 안내: 사용자가 "내보내기 / 분신 / 사본 / 복사본 만들어줘" 라고 해도 에이전트는 **"브랜치 만들기"** 로 통일 안내합니다. 사람 이름 예시는 **앨리스(또는 알리스) / 밥**.

자세한 흐름: 씨드(`seed/agentis.md`) §5 — "공유와 진화 — 브랜치 / 팩 / 메인".

### 씨드/키트 자체의 업그레이드 (v1.9)

표준 씨드가 v1.7/1.8 → v1.9 로 가도, **자기가 다듬은 두뇌·워크플로우·씨드는 덮어쓰지 않는다.**

키트 안전 병합:

```bash
# 기존 프로젝트의 agentis/ 에 새 키트 기능만 안전 병합
python install.py --target "<작업폴더>" --upgrade-kit
```

보호 규칙:
- 보존: `.clinerules/agentis.md`, `.clinerules/workflows/` 기존 사용자 수정본, `agentis/agent.md`, `agentis/memory/`, `agentis/skills/`, `agentis/graph/graph.html`, `agentis/graph/flow.html`, `agentis/graph/graph.json`, 루트 `workflows.html`, 루트 `holonomic-brain.html`
- 갱신: `# agentis-kit:` 마커가 있는 표준 스크립트/문서 (`build_flow.py`, `build_workflows.py`, `build_holonomic_brain.py`, `refresh_views.py`, 워크플로우 도구 등)는 `.upgrade-backups/` 에 백업 후 새 버전 반영
- 충돌: 소유권이 애매한 파일은 덮지 않고 `.kit-incoming/` 에 incoming 사본 보관

씨드 절 단위 병합:

```bash
# 1) 표준과 내 씨드 비교 — 절별 보고서 + plan.json 템플릿 생성
python agentis/workflows/씨드-업그레이드.py --check --from <표준씨드경로>

# 2) plan.json 의 각 절 action 결정 (take/keep/replace-with-file:<머지파일>) 후
python agentis/workflows/씨드-업그레이드.py --apply --plan plan.json --from <표준씨드경로>

# 3) 잘 다듬은 씨드를 메인 큐레이터에게 송신하고 싶을 때
python agentis/workflows/씨드-업그레이드.py --export-branch
```

핵심: 씨드 각 절에 박힌 `<!-- @section: N -->` 앵커가 키 → `UNCHANGED / NEW / LOCAL-CUSTOM / DIFF` 4분류 → 사람이 결정. 자세히: 씨드 §5-5.

## 능력치 — 진화가 눈에 보이게 (v1.2)

게임 캐릭터처럼 에이전트의 성장이 보입니다. 한 줄로 갱신:

```bash
python agentis/graph/agent-stats.py
```

출력 (예제 "규격이"):
```
 🧬  규격이 — Agentis Character Sheet
  Level: 7      XP: 800      생일: 2026-05-07 (7일째)
  ⚡ Speed     6   (스킬+워크플로우)
  🧠 INT      38   (기억·연결성)
  🎨 Variety  13   (작업·태그 다양성)
  💪 Stamina   7   (생존일수)
  🦉 Wisdom    0   (정비·추상화)
  🧬 감지된 도메인 유전자: 시험성적서 ×3 / 인증 ×2 / kc ×2 / rohs / 추출 / 스키마 / 대조 / 검증
```

같은 내용이 `agentis/memory/stats.md` 로도 저장되어 그래프에도 노드로 편입됩니다. **메인 후보 1차 판단**의 객관 지표이자 사용자 동기부여, 나아가 자연발생적 도메인 분류의 기초 데이터가 됩니다.

## 비전 — 에이전티스라는 세상

도구(v1.x) → 사내 표준 공유 체계(v2~3) → **에이전트들의 세상**(v4~). 누적된 능력치에서 자연발생적으로 도메인 "종(species)"이 분기되는 그림. 자세한 비전은 [`docs/vision-agentis-world.md`](./docs/vision-agentis-world.md).

## 상태

**v1.4 구현 완료** — v1.3의 모든 것 + **3D 두뇌 그래프 + 캐릭터 자산 동봉**:
- **3D 두뇌 그래프** — `build_graph.py` 가 Three.js + 3d-force-graph 를 인라인한 자체완결 `graph.html` 생성 (외부 의존 0, 1.3MB). 다크 테마 / 카테고리 색 / idle 자동 공전 / 노드 포커스 + 이웃 패널 / 범례 토글. **VS Code 의 Simple Browser** 로 사이드 탭에 띄우면 작업과 그래프 공존.
- **InfraNodus 효용의 사내 친화 자체완결 대응** — 외부 SaaS·계정·프록시 통과 불필요. 그래프 시각화의 핵심 효용을 그대로 흡수.
- **캐릭터 자산 동봉** (v1.4.1 적용 예정) — `graph/assets/characters/` 에 코부장(곰, Claude) / 오과장(개구리, Codex) / 젬대리(고양이, Gemini) SVG + 프로필. 다음 사이클에서 빌보드 sprite 로 그래프 씬에 합류.
- v1.3 의 키트 우선·씨드 폴백 / 씨드 자체의 절 단위 진화는 그대로.

모든 스크립트 실행 테스트 통과 (v1.3 공유 워크플로우 + v1.4 3D 그래프 정적 검증 15/15). 다음: 실제 사내 한 사이클(브랜치 송수신·리브랜드 + 3D 그래프 띄우기) 피드백 → v1.4.1 캐릭터 sprite. 진행: [`PLAN.md`](./PLAN.md) (v0.10). 메모: [`docs/llm-wiki-evolution.md`](./docs/llm-wiki-evolution.md) (LLM Wiki 보완 4대 방법론).

**v1.5 진행 중** — 딥인터뷰 분기, Hermes 자기진화 보강, Graph RAG + SQLite 인덱스, 업무 다이어그램, 캐릭터 빌보드 적용.
