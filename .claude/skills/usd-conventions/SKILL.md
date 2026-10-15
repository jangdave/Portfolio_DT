---
name: usd-conventions
description: 이 프로젝트의 USD 에셋/씬 작성 규칙(prim 경로, 단위, 축, dct: 메타데이터)을 적용하거나 검증할 때 사용. "USD 규칙", "prim 네이밍", "센서 메타데이터", "USD 내보내기" 요청에 사용.
---

# USD 규칙 (DC-Twin)

## 기본
- 단위 cm (`metersPerUnit = 0.01`), Up-axis Z, 기본 prim `/DC`.
- 에셋은 모듈별 파일(`usd/assets/*.usd`), 씬은 reference로 조립(`usd/scenes/*.usd`).

## prim 경로
```
/DC
  /Hall01
    /Row01/Rack_01 ... Rack_NN        (랙)
      /Server_U01 ... Server_UNN      (서버, 선택)
    /Cooling/CRAC_01 ...              (공조)
    /Power/PDU_01 ...                 (배전)
```
- 번호는 두 자리 이상 0 패딩, 영문 PascalCase + 언더스코어 번호.

## 커스텀 속성 (접두 `dct:`)
| 속성 | 타입 | 예 |
|---|---|---|
| `dct:assetType` | token | rack, server, crac, pdu |
| `dct:sensorId` | string | `H01-R01-RK01-TEMP-IN` |
| `dct:zone` | token | cold_aisle, hot_aisle |

- `dct:sensorId`는 MQTT 토픽의 `{asset}/{metric}`과 1:1 매핑된다 (`dct/{hall}/{asset}/{metric}`).

## 파일 종류 두 가지
| 종류 | 설명 | 검사 옵션 |
|---|---|---|
| 장면(scene) | `/DC` 아래에 홀, 랙, 설비를 모두 조립한 파일. 기본값 | `--kind scene` |
| 에셋(asset) | 랙 1기처럼 한 부품만 담은 파일. 기본 prim 이름은 자유(예: `Rack`)이고, 그 prim에 `dct:assetType`이 있어야 한다. 센서 ID는 장면에서 붙이므로 없어도 된다. | `--kind asset` |

## 검사하는 규칙 (오류 번호)
| 번호 | 내용 |
|---|---|
| U000 | 파일을 열 수 없음 |
| U101 / U102 / U103 | 단위(cm), 위쪽 축(Z), 기본 prim(장면은 `DC`) |
| U201 | 에셋의 기본 prim에 `dct:assetType`이 없음 |
| U202 / U203 | 장비 이름(Rack, Server_U, CRAC, PDU + 번호)인데 `dct:assetType`이 없음 / 값이 올바르지 않음 |
| U301 / U302 | 장면의 계층 이름(Hall##, Row##, Cooling, Power) / 종류별 경로 규칙 |
| U401 / U402 / U403 | 랙·CRAC·PDU의 센서 ID 누락 / 형식 오류 / 중복 |
| U501 | `dct:zone` 값 오류 |

센서 ID 형식: `H` + 두 자리 숫자로 시작하고 `-`로 이어지는 대문자·숫자 조각. 예: `H01-R01-RK01-TEMP-IN`

## 검증 방법
```
cd scripts/usd_tools
uv run --python 3.13 python validate_usd.py <파일.usda>
uv run --python 3.13 python validate_usd.py --kind asset <에셋.usda>
uv run --python 3.13 python -m pytest        # 검증기 자체 테스트
```
- 오류가 있으면 종료 코드 1, 없으면 0. 예시 파일은 `scripts/usd_tools/examples/`에 있다.
- 규칙을 바꾸면 `validate_usd.py`, 테스트, 이 문서를 함께 고친다.
- 변환 손실(E1) 기록(`docs/03_experiments.md`)에 갱신할 항목이 있는지도 확인한다.
