# graph/ — 두뇌 그래프

`memory/` 의 마크다운 위키를 노드/엣지 그래프로 만들어, 지식이 쌓이는 모습을 Obsidian 그래프 뷰처럼 보여줍니다.

## 빌드

```bash
python agentis/graph/build_graph.py            # graph.json + graph.html 생성
python agentis/graph/build_graph.py --open     # 생성 후 브라우저로 graph.html 열기
python agentis/graph/build_graph.py --memory <경로> --out <경로>   # 경로 지정
```

만들어지는 것:
- `graph.json` — 노드(페이지)·엣지(`[[링크]]`)·통계. 결정론적(같은 memory → 같은 json).
- `graph.html` — **자체완결형**. D3·CDN 등 외부 의존 없음 → 사내망/오프라인에서도 열림. 드래그=이동, 휠=확대, 노드 드래그=고정, 노드 클릭=이웃 강조. 카테고리별 색(CORE/CONCEPTS/ENTITIES/SOURCES/SKILLS), 연결 많은 허브 노드는 크게.

## 언제 갱신하나

`memory/` 가 바뀔 때마다 (= 작업이 끝날 때마다). 커널 작업 루프 §3-6 에 들어있습니다.

## graphify (선택 — 더 풍부하게)

`graphify`(Python, MIT)가 설치돼 있으면 의미관계 추출·커뮤니티 클러스터링·중심 노드 강조까지 얻을 수 있습니다. 에이전트가 사용자에게 `pip install graphify-kg`(또는 해당 패키지) 설치 가능한지 확인 후 `memory/` 를 먹입니다. 사내망에서 설치가 안 되면 위의 `build_graph.py` 로 충분합니다 — 그게 기본 경로입니다.

> 참고: https://github.com/safishamsi/graphify · https://graphify.net/
