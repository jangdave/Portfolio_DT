# 01. 아키텍처 / 설계 (러프)

> 상태: 초안 v0.1 (2026-10-15). 구현 전 계획이며 Phase 진행 중 ADR로 수정한다.

## 1. 한 줄 정의
Blender로 직접 모델링한 **가상 데이터센터**를 OpenUSD로 정의하고, Omniverse 계열 도구로 데이터를 생성하며, Unreal 5.7 클라이언트(UMG/CommonUI + 일부 웹 패널, Pixel Streaming)로 운영 화면을 구현한다.

## 2. 왜 Omniverse + Unreal인가 (역할 분리)
| | 시뮬레이션/저작 | 운영자 클라이언트 |
|---|---|---|
| 요구 | 씬 조립, 데이터 생성, 물리/센서 | 낮은 지연 UI, 알람, 다수 사용자 배포 |
| 도구 | Blender, OpenUSD, Omniverse Libraries | Unreal 5.7 (C++, CommonUI, PixelStreaming2) |
- "UE가 우월하다"가 아니라 **운영자용 클라이언트라는 용도에서의 선택**이며, 같은 씬을 Omniverse 단독 뷰어(ovrtx)로도 구현해 비교한다(`03_experiments.md`).

## 3. 데이터 경로 3종
| # | 경로 | 내용 | 방식 |
|---|---|---|---|
| 1 | 정적 씬 | 건물·랙·설비 계층, 센서 바인딩 메타데이터 | Blender → USD → UE 임포트 |
| 2 | 베이크 시뮬레이션 | 열/기류 볼륨, 설비 애니메이션 | 생성(Python/Blender) → VDB/캐시 → UE 재생 |
| 3 | 실시간 데이터 | 온도, 전력, 팬 속도, 알람 | 시나리오 생성기 → MQTT → Gateway → WebSocket → UE |

## 4. 구성도
```
[Blender 5.1]  모듈형 에셋(랙, CRAC, PDU, 배관) ──export──▶ [USD 에셋/씬]  (prim 경로 + dct: 메타)
                                                             │
                  ┌──────────────────────────────────────────┤
                  ▼                                           ▼
 [Omniverse Libraries: ovrtx/ovphysx]               [UE 5.7 DCTwin]
   · 레퍼런스 뷰어(비교 실험 B안)                       · USD 임포트, 센서-에셋 바인딩
   · (선택) 합성 데이터/물리                             · 히트맵, 알람 하이라이트, 기류 볼륨
                                                         · CommonUI 패널 + 웹 패널(데이터 채널)
 [sim/ 시나리오 생성기] ─MQTT─▶ [Mosquitto] ─▶ [gateway(Node)] ─WebSocket/REST─▶ UE
 [sim/ 열·기류 생성] ─VDB─▶ UE 볼류메트릭                  └▶ PixelStreaming2 ─WebRTC─▶ 브라우저
```

## 5. 컴포넌트 설계
### 5.1 USD 씬 (`usd/`)
- 계층: `/DC/Hall01/Row01/Rack_01/Server_U12`, 설비 `/DC/Hall01/Cooling/CRAC_01`
- 커스텀 속성: `dct:assetType`(rack|server|crac|pdu), `dct:sensorId`, `dct:zone`
- 단위 cm, Z-up. 에셋은 모듈별 파일, 씬은 reference로 조립.

### 5.2 센서 시나리오 생성기 (`sim/sensors/`)
- 시나리오: `normal`, `cooling_failure`(CRAC 정지 → 인접 랙 온도 상승), `power_spike`, `fan_fault`
- 간단한 열 모델(1차 지연 + 이웃 전파)로 값 생성. 시드 고정으로 재현 가능.
- MQTT 발행: 토픽 `dct/{hall}/{asset}/{metric}`, 페이로드 `{ts, value, unit, quality, scenario}`

### 5.3 열·기류 시각화 데이터 (`sim/thermal/`)
- 1차안: Python으로 저해상도 3D 온도장 생성 → OpenVDB 변환 → UE Sparse Volume Texture.
- 대안: Blender Mantaflow 연기 캐시(VDB). 선택은 Phase 2에서 PoC 후 ADR로 결정.
- 표기: "시각화 목적의 시뮬레이션, 공학적 CFD 아님". 정밀 해석이 필요하면 FDS/OpenFOAM은 확장 과제.

### 5.4 Gateway (`gateway/`)
- MQTT 구독 → 최근값 캐시 → WebSocket 푸시, 이력은 REST. UE는 MQTT 라이브러리 없이 내장 WebSockets 모듈 사용.
- 웹 패널도 동일 게이트웨이를 사용한다.

### 5.5 UE 클라이언트 (`unreal/`, 모듈 `DCTwin`)
| 계층 | 역할 |
|---|---|
| Core | 서브시스템, 설정, 로깅 |
| Data | WebSocket 클라이언트, SensorRegistry, 이력 버퍼, 시나리오 이벤트 |
| World | USD 스테이지 로딩, 센서-에셋 바인딩, 히트맵/하이라이트, 볼륨 액터 |
| UI | CommonUI 기반 Foundation → Components → Panels(Alarm, Sensor, Trend, Scenario) |
| Streaming | PixelStreaming2 설정, 데이터 채널 브리지, 접속/해상도 정책 |
- 새로 작성한다. 회사 프로젝트의 클래스·구조를 복사하지 않고 아이디어만 참고한다.

### 5.6 서비스 방식
- **주력:** Pixel Streaming(웹). **기준선:** Windows 패키징(exe). **비교 대상:** Omniverse(ovrtx) 뷰어.
- **UI:** UMG/CommonUI 기본 + 일부 패널(트렌드 차트 등)을 웹으로 구현해 데이터 채널로 연동하는 혼합안. 1~2개 패널로 A/B 비교 후 확정(ADR).
- **제외:** 모바일 네이티브, XR (사유: 주제와 거리, 분기 비용).

## 6. 보여줄 데모 시나리오
1. 정상 가동 → 랙 온도 히트맵, 전력 추이
2. CRAC 고장 주입 → 온도 상승 → 임계 알람 → 3D 하이라이트 + 기류 볼륨 변화
3. 알람 패널에서 원인 설비로 카메라 이동, 이력 확인
4. (선택) LLM 에이전트가 알람 요약·조치 제안

## 7. 범위 밖 (명시)
실제 CFD 정확도 주장, 모바일/XR, 멀티 테넌트 인증, 상용 수준 확장성. 필요 시 "향후 과제"로 문서화.

## 8. 열린 질문 (Phase 1에서 확인)
- Omniverse Kit 앱 설치 필요 여부(현재 Libraries만 존재). 합성 데이터/Isaac이 필요해질 때 결정.
- UE 5.7 USD 임포트(USD Importer 플러그인) 지원 범위와 변환 손실.
- UE 5.7의 VDB(Sparse Volume Texture) 임포트 워크플로.
- Mosquitto 설치 방식(Windows 네이티브 vs WSL).
