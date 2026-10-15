# ADR-010: Unreal Engine은 5.8로 진행한다

- 상태: 채택 (2026-10-15)
- 관련: [ADR-001](ADR-001-roles-omniverse-vs-unreal.md), [05 환경 상태](../05_env_status.md), [실증 결과 E0](../../experiments/results/E0_omniverse_capability_probe.md)

## 배경
처음에는 UE 5.7.4로 설계했고 열 볼륨 가져오기 시험(R6)도 5.7.4에서 했다. 사용자가 UE 5.8로 진행하기로 했고, 5.8.3(`++UE5+Release-5.8`, Changelist 58210709)을 2026-10-15에 설치했다.

## 결정
새 Unreal 프로젝트(`unreal/DataCenter_DT/DataCenter_DT.uproject`)는 **UE 5.8**로 만든다. 프로젝트와 C++ 모듈 이름은 사용자가 정한 `DataCenter_DT`를 그대로 쓰고, 클래스 접두 `DCT`와 계층(Core, Data, World, UI, Streaming)은 유지한다. 처음 설계의 `DCTwin`은 이 이름으로 바뀌었다. 5.7.4와 5.5.4는 설치된 채로 두지만 이 프로젝트는 쓰지 않는다.

## 확인한 것 (2026-10-15, 5.8.3, 임시 프로젝트에서 시험 후 삭제)
- 플러그인 파일이 있다: Interchange, InterchangeOpenVDB, InterchangeOpenUSD, USDImporter, PythonScriptPlugin(Experimental 아래), EditorScriptingUtilities.
- 랙 60기 홀 시뮬레이션 결과 VDB 30프레임(번호가 이어지는 `Name_000.vdb`...)을 기존 에셋 가져오기 경로(`AssetImportTask`)로 가져오면 **`AnimatedSparseVolumeTexture` 30프레임으로 묶인다.** 5.7.4와 같다.
- 전용 볼륨 머티리얼 3개, 머티리얼 인스턴스, 레벨 3개(원본, X 뒤집기, Y 뒤집기)를 Python으로 만들고 저장했다. 속성 지정 실패 없음. 5.7.4와 같은 결과다.
- 레벨 저장이 끝난 뒤 **엔진 종료 단계에서 접근 위반 오류(종료 코드 3)가 난다.** 5.7.4에서도 같은 증상이었고(Niagara 쪽 호출 목록) 만들어진 에셋에는 영향이 없다. 원인은 확인하지 않았다.

## USD 장면 가져오기 시험 (2026-10-15, 5.8.3, `hall01.usda`, 랙 60기 장면)
시험 스크립트: `experiments/omniverse_probe/ue/probe_usd_import.py`, 실행기 `run_usd_probe.ps1`, 결과 `experiments/omniverse_probe/out/ue58_usd_probe.json`.

| 방법 | 결과 |
|---|---|
| Interchange 가져오기(`AssetImportTask`) | 에셋 1,840개(StaticMesh 1,636, MaterialInstanceConstant 204)를 만든다. **레벨 액터는 만들지 않는다.** 장비마다 메시가 따로 생겨 개수가 많다. |
| USD Stage 액터(`UsdStageActor`) | 장면을 열어 `OPENED_AND_LOADED`가 된다. 기본 설정은 prim 종류로 컴포넌트를 합쳐서 `DC_0` 하나만 남는다. `use_prim_kinds_for_collapsing`을 끄면 컴포넌트 3,572개가 생기고 **Rack_ 60, CRAC_ 8, Sensor_ 204가 장면과 정확히 같다.** |

- **좌표 Y 부호가 뒤집힌다.** 장면의 `Rack_01`은 (x 280, y +150) cm인데 Stage 액터에서는 월드 위치가 (280, **-150**, 0)이다. USD(오른손 좌표계)에서 Unreal(왼손 좌표계)로 바뀌면서 Y가 뒤집힌 것으로 보인다. 다른 장비는 측정하지 않았다.
- **영향(아직 화면으로 확인 안 함, 계산으로 본 추정)**: 열 볼륨은 격자 인덱스가 Unreal의 +Y로 놓이므로 USD 장면과 겹치려면 Y를 뒤집은 데이터(`FY`)를 쓰고 볼륨 액터를 y = -홀 길이(-1360 cm)에 놓아야 맞을 것이다.
- **`dct:` 사용자 속성은 수집되지 않았다.** `metadata_options`의 수집 옵션(`collect_metadata`, `collect_on_components`, `collect_from_entire_subtrees`)을 켜고 열었지만 `UsdAssetUserData`의 메타데이터 맵이 비어 있었다. 설정 방법이 틀렸을 수 있어 이것이 불가능하다는 결론은 아니다. 우리 설계(ADR-005)는 센서를 매니페스트 JSON과 앵커 이름·경로로 연결하므로 런타임 속성 접근이 필수는 아니다. 앵커 이름(`Sensor_TEMP_IN`)은 컴포넌트 이름으로 보이고(`Sensor_TEMP_IN_0`처럼 `_0`이 붙음), 부모 경로를 따라 장비를 찾을 수 있다.

## 확인하지 못한 것
- USD `dct:` 사용자 속성을 런타임에 읽는 방법(위 시험에서는 수집되지 않음, 다른 설정이나 Python/C++ API 확인 필요)
- Y 반전 보정 후 볼륨이 장비와 겹치는지 화면 확인
- Stage 액터의 로드 시간과 프레임 속도(컴포넌트 3,572개)
- 5.8에서 볼륨이 장비와 같은 위치와 크기로 그려지는지 화면 확인(에디터에서 사용자가 직접 확인해야 한다. 자동 화면 캡처가 안 됨)
- PixelStreaming2, CommonUI, Nanite 등 5.8의 동작과 5.7 대비 변경점
- 5.8의 공식 문서와 릴리스 노트는 읽지 않았다. 위 내용은 설치 파일 확인과 직접 실행 결과만 근거로 한다.

## 영향
- 문서(`CLAUDE.md`, 01, 02, 05, 12), `scripts/check_env.ps1`, UE 시험 실행 스크립트(`ue/run_hall60_demo.ps1`의 기본 엔진 경로)를 5.8로 바꿨다.
- 과거 시험 기록(E0)과 설계 재점검(08)은 당시 5.7.4 기준이라 고치지 않았다.
- `build_heat_demo.py`의 엔진 소스 확인 사실(SVT 파라미터 이름, 볼륨 영역 규칙)은 5.7.4 소스 기준이며, 5.8 소스는 읽지 않았다. 동작 결과만 같은 것을 확인했다.

## 대안
- 5.7.4 유지: 이미 시험한 환경이지만, 사용자가 5.8을 원했고 5.8에서도 같은 시험이 통과했다.
