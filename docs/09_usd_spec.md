# 09. USD 규격 (v2)

- 상태: 채택 (2026-10-15). 검증 스크립트와 규칙 문서는 [이슈 #10](https://github.com/jangdave/Portfolio_DT/issues/10)에서 이 규격에 맞춘다.
- 목적: 3D 에셋과 장면을 어떤 구조와 이름으로 만들지 정한다. 모델링하는 사람, 스크립트를 쓰는 사람, Unreal 클라이언트를 만드는 사람이 같은 약속을 쓰게 한다.
- 관련 문서: [08 설계 재점검](08_design_review.md), [10 모델링 가이드](10_modeling_guide.md), [11 데이터 규격](11_data_spec.md)
- 용어는 [용어집](07_glossary_and_writing_rules.md)을 따른다.

## 1. 파일 종류

| 종류 | 설명 | 위치 | 만드는 방법 |
|---|---|---|---|
| 에셋(asset) | 랙 1기, CRAC 1기처럼 부품 하나를 담은 파일 | `usd/assets/` | Blender → 내보내기 → 마무리 스크립트 |
| 장면(scene) | 에셋을 홀에 배치한 파일 | `usd/scenes/` | 장면 생성 스크립트(`build_scene.py`) |

- 장면은 손으로 고치지 않는다. 배치를 바꾸려면 설정 파일을 고치고 스크립트를 다시 실행한다.
- 파일 형식은 텍스트(`.usda`)를 기본으로 한다. 바뀐 내용을 Git에서 읽을 수 있기 때문이다. 용량이 커지면 `.usdc`(Git LFS)로 바꾼다.

## 2. 기본 설정 (모든 파일 공통)

| 항목 | 값 | 이유 |
|---|---|---|
| 단위 | cm (`metersPerUnit = 0.01`) | Unreal의 기본 단위가 cm라서 크기 변환이 필요 없다. |
| 위쪽 축 | Z (`upAxis = "Z"`) | Unreal과 같다. |
| 기본 prim | 에셋은 에셋 이름(예: `Rack`), 장면은 `DC` | 다른 파일에서 참조하기 쉽다. |
| 좌표 | 에셋은 **바닥 중앙이 원점**, 앞쪽이 -Y | 배치할 때 위치 계산이 쉽다. |

## 3. 장면의 계층 구조

```
/DC                                  (기본 prim)
 └─ Hall01
     ├─ Row01
     │   ├─ Rack_01 ... Rack_10      (랙, 홀 안에서 번호를 이어서 매긴다)
     │   └─ ...
     ├─ Row02
     │   └─ Rack_11 ... Rack_20
     ├─ Cooling
     │   └─ CRAC_01 ... CRAC_04
     └─ Power
         └─ PDU_01 ... PDU_04
```

| 규칙 | 내용 |
|---|---|
| 이름 형식 | 영문 대소문자와 `_`, 번호는 **두 자리 이상**(`Rack_01`) |
| 번호 범위 | 장비 번호는 **홀 안에서 겹치지 않는다.** `Row02`의 첫 랙은 `Rack_01`이 아니라 `Rack_11`이다. |
| 장비 종류 | rack, server, crac, pdu |
| 경로 | rack: `/DC/Hall##/Row##/Rack_##`, server: 랙 아래 `Server_U##`, crac: `/DC/Hall##/Cooling/CRAC_##`, pdu: `/DC/Hall##/Power/PDU_##` |

## 4. 센서 앵커

센서 하나는 **prim 하나(센서 앵커)** 로 나타낸다. 장비 아래 `Anchors` 그룹에 둔다.

```
/DC/Hall01/Row01/Rack_01
 └─ Anchors
     ├─ Sensor_TEMP_IN      (입구 온도)
     ├─ Sensor_TEMP_OUT     (출구 온도)
     └─ Sensor_POWER        (전력)
```

| 속성 | 타입 | 예 | 설명 |
|---|---|---|---|
| `dct:assetType` | token | `sensor` | 센서 앵커 표시 |
| `dct:sensorId` | string | `H01-RK01-TEMP-IN` | 센서를 구분하는 값. 경로에서 만든다(5장). 장면에서만 붙인다. |
| `dct:metric` | token | `temp_in` | 측정 종류. 소문자와 `_` |
| `dct:unit` | string | `degC` | 단위 |

- 앵커의 **위치**가 센서의 3D 위치다. 화면에서 센서 표시나 알람 표시를 붙이는 기준점이 된다.
- 에셋 파일의 앵커에는 `dct:sensorId`가 없다. 같은 랙 에셋을 20번 쓰기 때문에, ID는 장면을 만들 때 인스턴스마다 붙인다(6장).
- 장비(rack, crac, pdu)는 센서 앵커를 **하나 이상** 가진다. 서버(server)는 센서가 없어도 된다.

### 장비별 센서 목록 (기본)

| 장비 | 센서 | 측정 종류(`dct:metric`) | 단위 |
|---|---|---|---|
| rack | 입구 온도, 출구 온도, 전력 | `temp_in`, `temp_out`, `power` | `degC`, `degC`, `kW` |
| crac | 공급 온도, 회수 온도, 팬 속도 | `supply_temp`, `return_temp`, `fan_speed` | `degC`, `degC`, `percent` |
| pdu | 전력, 부하율 | `power`, `load` | `kW`, `percent` |

랙 20기 x 3 + CRAC 4기 x 3 + PDU 4기 x 2 = **센서 80개**.

## 5. 이름과 ID 규칙

한 번 정하면 USD 경로, 센서 ID, MQTT 주소를 서로 계산해서 만들 수 있다.

| 항목 | 규칙 | 예 |
|---|---|---|
| USD 경로 | 3장, 4장 | `/DC/Hall01/Row01/Rack_01/Anchors/Sensor_TEMP_IN` |
| 센서 ID | `H` + 홀 번호 + `-` + 장비 코드 + 장비 번호 + `-` + 측정 종류(대문자, `_`는 `-`) | `H01-RK01-TEMP-IN` |
| MQTT 주소 | `dct/v1/` + 홀 + `/` + 장비 이름 + `/` + 측정 종류 (모두 소문자) | `dct/v1/hall01/rack_01/temp_in` |

장비 코드: rack = `RK`, crac = `CR`, pdu = `PD`

**변환 예시**
```
USD 경로  /DC/Hall01/Row01/Rack_01/Anchors/Sensor_TEMP_IN
  홀 = Hall01 → hall01, 홀 번호 01
  장비 = Rack_01 → rack_01, 코드 RK, 번호 01
  측정 종류 = temp_in
센서 ID   H01-RK01-TEMP-IN
MQTT 주소 dct/v1/hall01/rack_01/temp_in
```
- 장비 번호가 홀 안에서 겹치지 않기 때문에 줄(Row) 번호는 ID에 넣지 않는다.
- 이 변환은 코드 한 곳(센서 매니페스트 생성 스크립트, [이슈 #12](https://github.com/jangdave/Portfolio_DT/issues/12))에만 두고, 다른 곳에서는 변환을 다시 구현하지 않는다.

## 6. 장면 만들기: 참조와 덮어쓰기

장면 생성 스크립트가 에셋을 **참조(reference)** 해서 배치하고, 센서 앵커에 ID를 **덮어쓴다(override)**.

```usda
def Xform "Rack_01" (
    references = @../assets/rack.usda@
)
{
    double3 xformOp:translate = (-120, 0, 0)
    uniform token[] xformOpOrder = ["xformOp:translate"]

    over "Anchors"
    {
        over "Sensor_TEMP_IN"
        {
            string dct:sensorId = "H01-RK01-TEMP-IN"
        }
    }
}
```

| 장점 | 설명 |
|---|---|
| 에셋 하나를 고치면 모든 인스턴스가 바뀐다 | 랙 모델링을 개선해도 장면을 다시 만들 필요가 없다. |
| 센서 ID가 장면에만 있다 | 에셋은 어디서든 재사용할 수 있다. |
| 같은 설정이면 같은 결과 | 설정 파일과 스크립트만 있으면 장면을 다시 만들 수 있다. |

## 7. 재질

| 재질 이름 | 용도 |
|---|---|
| `M_RackFrame` | 랙 프레임 (어두운 금속) |
| `M_ServerBody` | 서버 몸체 |
| `M_ServerFront` | 서버 **앞면 패널**. 온도에 따라 색을 바꾸는 부분이므로 **반드시 별도 재질 칸**으로 둔다. |
| `M_Door` | 문 (있는 경우) |

- Blender의 Principled BSDF 재질은 USD로 나갈 때 `UsdPreviewSurface`로 바뀐다. 복잡한 노드는 바뀌지 않으므로 단순한 값(색, 금속성, 거칠기)만 쓴다.
- 온도 색 표시는 재질을 바꾸지 않고 Unreal에서 **인스턴스별 값**(Custom Primitive Data)으로 처리한다. ([12](12_unreal_design.md) 5장)

## 8. 속성 정리

| 속성 | 타입 | 붙는 곳 | 필수 |
|---|---|---|---|
| `dct:assetType` | token (`rack`, `server`, `crac`, `pdu`, `sensor`) | 장비, 센서 앵커, 에셋의 기본 prim | 필수 |
| `dct:sensorId` | string | 센서 앵커 (장면) | 장면에서 필수 |
| `dct:metric` | token | 센서 앵커 | 필수 |
| `dct:unit` | string | 센서 앵커 | 필수 |
| `dct:zone` | token (`cold_aisle`, `hot_aisle`) | 랙, 센서 앵커 | 선택 |

Blender에서 사용자 속성으로 만들면 USD에는 string으로 나온다. `finalize_asset.py`가 `assetType`, `zone`, `metric`을 token으로 바꾼다.

## 9. 검증 규칙의 변경 (v1 → v2)

| 번호 | v1 | v2 |
|---|---|---|
| U203 | assetType 값: rack, server, crac, pdu | `sensor` 추가 |
| U401 | rack, crac, pdu에 `dct:sensorId` 필수 | rack, crac, pdu는 **센서 앵커를 하나 이상** 가져야 함 |
| U402 | 센서 ID 형식 | 센서 앵커의 센서 ID 형식, 그리고 **경로에서 만든 값과 같은지** |
| U403 | 센서 ID 중복 | 같음 |
| (새) U404 | - | 센서 앵커에 `dct:metric`, `dct:unit` 필수, 앵커 이름(`Sensor_<METRIC>`)과 `dct:metric` 일치 |

## 10. 에셋 목록

| 에셋 | 파일 | 상태 |
|---|---|---|
| 랙 | `usd/assets/rack.usda` | 블록아웃 완료(삼각형 312개). 센서 앵커 2개(v1 형식)이며 v2로 고쳐야 한다. 직접 모델링 예정 ([이슈 #4](https://github.com/jangdave/Portfolio_DT/issues/4)) |
| CRAC | `usd/assets/crac.usda` | 예정 (Phase 2) |
| PDU | `usd/assets/pdu.usda` | 예정 (Phase 2) |
| 홀 외피(바닥, 벽, 천장) | 별도 에셋 없음 | 장면 생성 스크립트가 상자로 생성 (Phase 2) |

## 11. 방(홀)과 둘러보기 규격 (초안 v2.1)

내부 둘러보기([12](12_unreal_design.md) 10장)를 위해 방을 걸어 다닐 수 있게 만들고, 안내 투어 지점을 USD로 정의한다. 검증 스크립트에는 이 규격이 확정된 뒤 반영한다.

### 11.1 홀 외피 (바닥, 벽, 천장)
데이터센터 내부가 곧 장면이므로 **방을 따로 모델링하지 않는다.** 걸어 다니는 데 필요한 바닥, 벽, 천장은 장면 생성 스크립트(`build_scene.py`, [이슈 #11](https://github.com/jangdave/Portfolio_DT/issues/11))가 **기본 도형(상자)으로 만든다.** 모양을 다듬는 작업은 시간이 남을 때의 개선 항목이다.

| 항목 | 값 | 설명 |
|---|---|---|
| 홀 크기 | 약 12 x 9 x 3.5 m | 랙 2줄 x 10기와 통로 포함. 배치 설정 파일에서 정하고 이 문서를 고친다. |
| 차가운 통로 폭 | 120 cm 이상 | 두 랙 줄의 서버 앞면 사이 |
| 뜨거운 통로 폭 | 100 cm 이상 | 두 랙 줄의 뒷면 사이 |
| 바닥 | 상자 하나 + 타일 무늬 텍스처 | 이중 바닥 느낌은 텍스처로 표현 |
| 벽, 천장 | 상자 | 열 시뮬레이션의 막힌 곳 정보로도 쓴다([13](13_omniverse_research.md) 3장). |
| 조명 | 천장 조명 몇 개 | Unreal에서 설정해도 된다. |

### 11.2 충돌
- 외피(바닥, 벽, 천장)가 이미 상자라서 **그 자체를 충돌로 쓴다.** 별도 충돌 형상이 필요 없다.
- 랙은 에셋 안의 `Collision` 그룹에 상자(`Col_<대상>`)를 둘 수 있다. 필요한지는 Phase 2의 E1에서 확인한다(랙 외형이 단순해서 불필요할 수도 있다).

### 11.3 투어 앵커
안내 투어의 지점 하나는 **투어 앵커 prim** 하나다. `/DC/Hall01/Tour` 아래에 둔다.

```
/DC/Hall01/Tour
 ├─ View_01   (정문에서 본 홀 전체)
 ├─ View_02   (차가운 통로)
 └─ View_03   (냉각 장치 앞)
```

| 속성 | 타입 | 설명 |
|---|---|---|
| `dct:assetType` | token = `viewpoint` | 투어 앵커 표시 |
| `dct:title` | string | 지점 제목 (패널에 표시) |
| `dct:description` | string | 설명 |
| `dct:focus` | string (선택) | 강조할 장비 이름. 예: `CRAC_02` |
| 위치·방향 | Xform | 카메라가 서는 위치와 보는 방향 |

- 지점 순서는 이름의 번호 순서(`View_01`, `View_02`, ...)다.
- 투어 앵커는 센서 매니페스트와 같은 방식으로 **투어 목록 JSON**으로 뽑아 Unreal이 읽는다([ADR-005](decisions/ADR-005-sensor-anchors-and-manifest.md)의 방식을 확장).

## 12. 건물 외관과 층 (v2.2 초안, ADR-008)

첫 화면은 건물 외관이고 건물을 누르면 한 층(서버 랙 공간)으로 들어간다. **기존 `/DC/Hall01/...` 구조는 그대로 두고**, 건물을 옆에 추가한다. 센서 ID와 검증 규칙이 바뀌지 않게 하려는 것이다.

```
/DC
 ├─ Building01                       (assetType = building)
 │   ├─ Exterior                     (외벽, 지붕, 출입구, 환기구: 외관용 모양)
 │   ├─ Floors                       (층 표시용 단순 모양, 선택 가능한 층은 표시)
 │   └─ Outdoor                      (옥외 설비: 냉각탑, 발전기, 변전 설비)
 └─ Hall01                           (서버 랙 공간, 3층에 해당)
     └─ ... (3장의 구조 그대로)
```

| 속성 | 붙는 곳 | 설명 |
|---|---|---|
| `dct:assetType = "building"` | `Building01` | 건물. 클릭 대상 |
| `dct:title` | `Building01` | 화면에 표시할 이름 |
| `dct:floor` (정수) | `Hall01` | 이 홀이 있는 층 번호. 외관 화면에서 어느 층이 열리는지 정한다. |
| `dct:assetType = "outdoor"` | 옥외 설비 | 냉각탑, 발전기 등 |

- **자세히 만드는 층은 하나**(`Hall01`)이다. 다른 층은 외관 안쪽을 가린 단순 모양이며 누를 수 없다(화면에 "준비 중" 표시 없이 비활성).
- 건물 외관과 옥외 설비는 **직접 모델링**한다. 외벽은 모듈형 패널로 만들어 반복해 쓴다.
- 외관 모델은 걸어 다니지 않으므로 충돌 형상이 필요 없고, 열 시뮬레이션에도 쓰이지 않는다. 외관 정보는 보기 위한 모양이다.
- 검증 스크립트는 `building`, `outdoor`를 `dct:assetType` 허용 값에 추가하고, `/DC` 바로 아래에 `Hall##`과 `Building##`을 모두 허용하도록 고친다([이슈 #10](https://github.com/jangdave/Portfolio_DT/issues/10)).
