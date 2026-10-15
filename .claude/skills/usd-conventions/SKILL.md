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

## 검증 체크
1. 단위/축이 위 규칙과 일치하는가
2. 모든 센서 보유 prim에 `dct:sensorId`가 있고 중복이 없는가
3. prim 경로가 규칙을 따르는가
4. 변경 시 `docs/03_experiments.md`의 E1(변환 손실) 기록을 갱신할 항목이 있는가

## 도구
`pxr`(usd-core)는 `sim/` uv 환경에 설치해 검증 스크립트(`scripts/validate_usd.py`)로 점검한다.
