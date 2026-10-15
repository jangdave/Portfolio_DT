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
| 바닥, 벽, 천장 | `usd/assets/room.usda` | 예정 (Phase 2) |
