# DC-Twin (가상 데이터센터 디지털 트윈) — 포트폴리오 프로젝트

## 목적
Omniverse(OpenUSD 기반 저작·시뮬레이션)와 Unreal Engine 5.7(운영자용 클라이언트)을 역할 분리해 연결한 **공개 가능한 소형 디지털 트윈**을 만든다.
목표 직군은 UE 클라이언트 개발자이며, 시뮬레이션/데이터 직군으로의 확장 가능성을 함께 보여준다.
설계 개요는 `docs/01_architecture.md`, 일정은 `docs/02_roadmap.md`, 비교 실험은 `docs/03_experiments.md`.

## 절대 규칙 (클린룸)
- 이 저장소는 **공개 포트폴리오용**이다. 재직 회사 프로젝트(`D:\UnrealProject\` 아래 업무 프로젝트)의 **코드·에셋·데이터·고객사/내부 명칭을 복사하거나 붙이지 않는다.** 금지어 목록은 저장소에 두지 않고 로컬 파일 `.claude/cleanroom-terms.local.txt`(gitignore)에 둔다.
- 해당 프로젝트는 **읽기 전용 참조**다. 설계 아이디어(계층 구조, 서비스 분리, 배포 절차)만 참고하고 **코드는 새로 작성**한다.
- 모델링은 직접 제작(Blender)한 **가상 시설**만 쓴다. 실제 시설 형상/도면/좌표/로고 금지.
- 시뮬레이션 결과는 "시각화 목적"으로 표기한다. 공학적 정확성을 주장하지 않는다(`docs/04_clean_room_policy.md`).
- `D:\UnrealProject\**`, `D:\omniverse-labs-main\**`는 수정하지 않는다(권한으로도 차단).

## 구조 요약
```
Blender → USD(prim 경로 + dct: 메타데이터) → Omniverse(ovrtx/ovphysx, 데이터 생성)
   ↘ 센서 시나리오 생성기(Python) → MQTT(Mosquitto) → Gateway(Node) → WebSocket
UE 5.7 클라이언트: USD 임포트 + WebSocket 수신 + CommonUI 패널 + PixelStreaming2(웹)
```
데이터 경로 3종: ① 정적 USD ② 베이크 캐시(VDB/애니메이션) ③ 실시간 MQTT. 상세는 설계 문서 참조.

## 디렉터리
| 경로 | 내용 |
|---|---|
| `docs/` | 기획·설계·로드맵·실험·정책, `docs/decisions/`(ADR) |
| `blender/` | .blend 원본, 내보내기 스크립트 |
| `usd/` | 내보낸 USD 에셋/씬 (`assets/`, `scenes/`) |
| `sim/` | 센서 시나리오 생성기, 열/기류 데이터 생성, Omniverse 스크립트 |
| `gateway/` | MQTT → WebSocket/REST 게이트웨이 (Node) |
| `unreal/` | UE 5.7 프로젝트 (`DCTwin.uproject`, 에디터에서 생성) |
| `web/` | 하이브리드 UI용 웹 패널 (일부 패널) |
| `experiments/` | 비교 실험 코드와 측정 결과 |
| `scripts/` | 환경 점검, 실행 보조 스크립트 |

## 컨벤션
- **USD 규칙**: prim 경로 `/DC/Hall{NN}/Row{NN}/Rack_{NN}/...`, 단위 cm, Up-axis Z, 커스텀 속성 접두 `dct:` (`dct:assetType`, `dct:sensorId`). 상세: `.claude/skills/usd-conventions`.
- **MQTT 토픽**: `dct/{hall}/{asset}/{metric}`, 페이로드는 JSON(`ts`, `value`, `unit`, `quality`, `scenario`).
- **UE C++**: 모듈 `DCTwin`, 계층 `Core / Data / World / UI / Streaming`. 접두 `DCT`. 새 코드만 작성, 회사 프로젝트 클래스명 재사용 금지.
- **Python**: `uv`로 환경 관리, 3.13 권장(`ovrtx` 휠 호환). 시스템 Python 3.14는 사용하지 않는다.
- **Git 워크플로**(`docs/06_workflow.md`): `main`에서 직접 작업하지 않는다. 작업 시작 시 `feat|fix|docs|chore|exp/<주제>` 브랜치를 먼저 만들고, Conventional Commits로 커밋(`type(scope)`는 영어 키워드, **제목·본문은 한글**: 예 `feat(sim): cooling_failure 시나리오 생성기 추가`), PR → Squash merge. 바이너리는 Git LFS. 사용자가 요청할 때만 commit/push/PR을 만든다. force push 금지.

## 작업 방식
- 단계는 `docs/02_roadmap.md`의 Phase 순서를 따른다. 각 Phase 끝에 산출물과 측정값을 `experiments/` 또는 `docs/`에 남긴다.
- 설계 결정은 `docs/decisions/ADR-XXX-*.md`에 한 장씩 기록한다(결정, 근거, 대안, 한계).
- 외부 도구(Omniverse, UE 플러그인)의 지원 상태는 시기별로 변하므로 **공식 문서로 확인한 날짜와 버전**을 기록한다.
- 환경 점검: `scripts/check_env.ps1`. 결과 기록: `docs/05_env_status.md`.

## 환경 (2026-10-15 확인)
RTX 5090 32GB / Ryzen 9 9950X3D / RAM 126GB / UE 5.7.4 / Blender 5.1 / Node, Git, uv, WSL 있음 / Mosquitto, Docker 없음.
Omniverse: Kit 앱 미설치, `ovrtx 0.3.0`·`ovphysx 0.3.7`(Omniverse Libraries)만 로컬 샘플 venv에 있음.
