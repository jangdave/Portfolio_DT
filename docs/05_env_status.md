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
| Unreal Engine | 5.7.4, 5.5.4 설치됨 |
| Blender | 5.1 설치됨 |
| Python | 시스템 3.14.0 (Omniverse 휠과 호환 불확실 → uv로 3.13 사용) |
| uv / Node / Git / WSL | 있음 |
| Mosquitto / Docker | 없음 (Phase 3 전에 설치 방식 결정) |

## Omniverse
| 항목 | 상태 |
|---|---|
| Omniverse Hub 1.1.0 | `%LOCALAPPDATA%\ov\pkg\hub-1.1.0` 존재(2025-12 설치, 잔재 수준) |
| Kit 앱 (USD Composer, Isaac Sim 등) | **미설치** (kit.exe 등 탐색에서 발견되지 않음) |
| Omniverse Libraries | `D:\omniverse-labs-main` 샘플 venv에 `ovrtx 0.3.0.312915`, `ovphysx 0.3.7` 설치됨 (Python 3.13.9) |
| 해석 | 현재 환경은 **Libraries 경로(Python에서 USD 로드·RTX 렌더·PhysX)** 로 사용 가능. Kit 앱 기반 기능(Replicator, Isaac Sim, Flow 등)은 필요 시 별도 설치 |

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
- [ ] UE 5.7 USD Importer 플러그인 상태
- [ ] Omniverse Kit 앱/Isaac Sim의 현재 설치 방식과 5090 지원 버전 (공식 문서 확인, 날짜 기록)
- [ ] Mosquitto 설치 방식 결정

## 이 프로젝트용 Python 환경
`sim/` 아래에서 `uv`로 Python 3.13 가상환경을 만든다. 시스템 3.14는 사용하지 않는다.
