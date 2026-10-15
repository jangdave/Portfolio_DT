"""USD 경로에서 센서 ID와 MQTT 주소를 계산하는 규칙 (09 USD 규격 5장, ADR-005).

이 변환은 **이 파일 한 곳에만** 둔다. 검증기(`validate_usd.py`)와 매니페스트 생성기(`build_manifest.py`)가 같이 쓴다.

    USD 경로  /DC/Hall01/Row01/Rack_01/Anchors/Sensor_TEMP_IN
    센서 ID   H01-RK01-TEMP-IN
    MQTT 주소 dct/v1/hall01/rack_01/temp_in
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SENSOR_PATH_RE = re.compile(
    r"^/DC/Hall(?P<hall>\d{2})/(?P<folder>(?:Row\d{2}/Rack|Cooling/CRAC|Power/PDU))_(?P<num>\d{2,})"
    r"/Anchors/Sensor_(?P<metric>[A-Z0-9_]+)$"
)
EQUIPMENT_CODES = {"Rack": "RK", "CRAC": "CR", "PDU": "PD"}  # 센서 ID의 장비 코드
EQUIPMENT_TYPES = {"Rack": "rack", "CRAC": "crac", "PDU": "pdu"}
TOPIC_ROOT = "dct/v1"  # 메시지 형식 버전. 형식이 바뀌면 v2로 올린다.


@dataclass(frozen=True)
class SensorPath:
    hall_no: str          # "01"
    equipment_kind: str   # "Rack", "CRAC", "PDU"
    equipment_no: str     # "01"
    metric_upper: str     # "TEMP_IN"

    @property
    def equipment_name(self) -> str:
        return f"{self.equipment_kind}_{self.equipment_no}"

    @property
    def sensor_id(self) -> str:
        return f"H{self.hall_no}-{EQUIPMENT_CODES[self.equipment_kind]}{self.equipment_no}-{self.metric_upper.replace('_', '-')}"

    @property
    def topic(self) -> str:
        return f"{TOPIC_ROOT}/hall{self.hall_no}/{self.equipment_name.lower()}/{self.metric_upper.lower()}"

    @property
    def equipment_type(self) -> str:
        return EQUIPMENT_TYPES[self.equipment_kind]


def parse_sensor_path(path: str) -> SensorPath | None:
    """센서 앵커 경로를 해석한다. 센서 앵커 경로가 아니면 None."""
    m = SENSOR_PATH_RE.match(path)
    if not m:
        return None
    kind = m.group("folder").rsplit("/", 1)[-1]  # "Row01/Rack" -> "Rack"
    return SensorPath(m.group("hall"), kind, m.group("num"), m.group("metric"))


def sensor_id_from_path(path: str) -> str | None:
    p = parse_sensor_path(path)
    return p.sensor_id if p else None
