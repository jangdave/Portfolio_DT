# 05. 환경 상태 (2026-10-15 점검)

## 하드웨어
| 항목 | 값 |
|---|---|
| GPU | NVIDIA GeForce RTX 5090, 32GB VRAM (드라이버 32.0.16.1692 보고값) |
| CPU / RAM | Ryzen 9 9950X3D (16C) / 126GB |
| 저장소 | C: 497GB 여유, D: 1,215GB 여유 |

## 소프트웨어
| 항목 | 상태 |
|---|---|
| Unreal Engine | **5.8.3**(주 사용), 5.7.4, 5.5.4 설치됨. 5.8.3은 2026-10-15 설치, Changelist 58210709, `++UE5+Release-5.8` |
| Blender | 5.1 설치됨 |
| Python | 시스템 3.14.0 (Omniverse 휠과 호환 불확실 → uv로 3.13 사용) |
| uv / Node / Git / WSL | 있음 |
| Mosquitto / Docker | 없음 (Phase 3 전에 설치 방식 결정) |

## Omniverse
| 항목 | 상태 |
|---|---|
| Omniverse Hub 1.1.0 | `%LOCALAPPDATA%\ov\pkg\hub-1.1.0` 존재(2025-12 설치, 잔재 수준) |
| Kit 앱 | **설치함 (2026-10-15)**: Kit SDK 110.4.0, `D:\omniverse-kit\kit-app-template`에서 `dctwin.base_editor` 앱을 빌드. RTX 5090에서 실행 확인(드라이버 616.92). 설치 용량 약 2.5GB(packman `D:\packman-repo` 0.82GB + 확장 캐시 `%LOCALAPPDATA%\ov\data` 증가 약 1.6GB). 첫 실행 239초, 이후 12초. 방법과 결과: `experiments/omniverse_probe/kit/README.md`, `experiments/results/E0_omniverse_capability_probe.md` |
| Kit 확장 | `omni.hydra.rtx`, `omni.graph.core`, `omni.warp.core`(Warp 1.17.0), `omni.physx.stageupdate`, `omni.flowusd` 110.0.4 확인 |
| USD Composer, Isaac Sim 등 다른 Kit 앱 | 미설치(필요하면 별도 설치) |
| Omniverse Libraries | `D:\omniverse-labs-main` 샘플 venv에 `ovrtx 0.3.0.312915`, `ovphysx 0.3.7` 설치됨 (Python 3.13.9) |
| 해석 | **Libraries 경로(Python에서 USD 로드·RTX 렌더·PhysX)** 와 **Kit 앱 경로(RTX 뷰포트, OmniGraph, Warp, Flow)** 모두 사용 가능. Replicator, Isaac Sim은 미설치 |

## ovrtx 스모크 테스트 결과 (2026-10-15, Phase 1)
직접 작성한 최소 씬(`experiments/p1_ovrtx_smoke/smoke_scene.usda`)을 `ovrtx 0.3.0`으로 렌더했다. **RTX 5090에서 정상 동작**한다.

| 항목 | 값 |
|---|---|
| 환경 | Python 3.13.9 (uv venv), ovrtx 0.3.0.312915, numpy 2.2.6, pillow 12.2.0 |
| 해상도 | 1280 x 720 (LdrColor) |
| Renderer 생성 | 24.7 s (최초 실행, 셰이더 캐시 생성) |
| 첫 프레임 | 53.8 s (최초 실행, 셰이더 컴파일 포함) |
| 이후 프레임(중앙값) | 7.1 ms (30프레임 기준, 읽기 포함) |
| VRAM | 1,893 → 5,316 MiB (약 3.4 GiB 증가) |
| 결과물 | `experiments/p1_ovrtx_smoke/out/smoke_render.png`, `smoke_result.json` |

- 최초 실행의 큰 지연은 셰이더 캐시 생성이며, 이후 실행은 캐시 덕에 짧아질 것으로 예상한다(재측정 필요).
- 한 번의 측정이라 성능 비교(E2)의 근거로는 쓰지 않는다. E2에서 조건을 통제해 다시 측정한다.
- 실행 명령: `cd experiments/p1_ovrtx_smoke && uv run --python 3.13 python smoke_test.py`

## 미확인 / 다음에 확인
- [x] `ovrtx`로 USD를 렌더해 5090(Blackwell)에서 동작하는지 → 위 결과로 확인
- [x] UE 5.8 플러그인 존재: Interchange, InterchangeOpenVDB, InterchangeOpenUSD, USDImporter, PythonScriptPlugin (2026-10-15, 파일 존재 확인). USD 가져오기는 Stage 액터로 동작 확인(ADR-010)
- [x] UE 5.8.3에서 열 볼륨 VDB 시퀀스 가져오기, 볼륨 머티리얼 레벨 생성 동작 → ADR-010 참고
- [ ] Omniverse Kit 앱/Isaac Sim의 현재 설치 방식과 5090 지원 버전 (공식 문서 확인, 날짜 기록)
- [ ] Mosquitto 설치 방식 결정

## 이 프로젝트용 Python 환경
`sim/` 아래에서 `uv`로 Python 3.13 가상환경을 만든다. 시스템 3.14는 사용하지 않는다.
