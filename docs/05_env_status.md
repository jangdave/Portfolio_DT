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

## 미확인 / 다음에 확인
- [ ] `ovrtx`로 샘플 USD를 실제 렌더해 5090(Blackwell)에서 동작하는지 (`scripts/check_env.ps1` 확장)
- [ ] UE 5.7 USD Importer 플러그인 상태
- [ ] Omniverse Kit 앱/Isaac Sim의 현재 설치 방식과 5090 지원 버전 (공식 문서 확인, 날짜 기록)
- [ ] Mosquitto 설치 방식 결정

## 이 프로젝트용 Python 환경
`sim/` 아래에서 `uv`로 Python 3.13 가상환경을 만든다. 시스템 3.14는 사용하지 않는다.
