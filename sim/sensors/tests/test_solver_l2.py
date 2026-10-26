"""L2 시험: 가짜 L1과 가짜 예측기로 연결(입력 만들기, 값 바꾸기, 구간·등급 붙이기, 되돌림)을 확인한다. Warp와 scikit-learn은 필요 없다."""
from __future__ import annotations

from types import SimpleNamespace

from dct_sensors.config import Config
from dct_sensors.generator import Generator
from dct_sensors.publish import MqttPublisher
from dct_sensors.scenarios import get
from dct_sensors.solver_l2 import L2Solver, rack_title
from dct_sensors.solvers import Controls, L0Solver


class FakeBase(L0Solver):
    flow_info = {"supply_m3s": 50.0, "aisle_leak_m3s": [1.0, 2.0]}


class FakePredictor:
    def __init__(self, fallback=False):
        self.calls = []
        self.fallback = fallback

    def predict(self, sample, ours, info):
        self.calls.append((sample, dict(ours), info))
        names = list(ours)
        if self.fallback:
            return SimpleNamespace(fallback=True, reason="전력 범위 밖", corrected=dict(ours), lower90=dict(ours), upper90=dict(ours), level={n: "fallback" for n in names})
        return SimpleNamespace(fallback=False, reason="", corrected={n: ours[n] + 1.0 for n in names}, lower90={n: ours[n] + 0.5 for n in names},
                               upper90={n: ours[n] + 1.5 for n in names}, level={n: "caution" for n in names})


class JumpingPredictor(FakePredictor):
    """처음에는 +1, 팬이 멈춘 뒤에는 +5를 보정으로 내는 가짜 예측기."""

    def predict(self, sample, ours, info):
        add = 5.0 if sample["fan"]["CRAC_01"] == 0.0 else 1.0
        names = list(ours)
        return SimpleNamespace(fallback=False, reason="", corrected={n: ours[n] + add for n in names}, lower90={n: ours[n] + add - 0.5 for n in names},
                               upper90={n: ours[n] + add + 0.5 for n in names}, level={n: "ok" for n in names})


def make(manifest, fallback=False):
    cfg = Config()
    pred = FakePredictor(fallback)
    return cfg, pred, L2Solver(manifest, cfg, base=FakeBase(manifest, cfg), predictor=pred)


def test_rack_title():
    assert rack_title("rack_07") == "Rack_07"


def test_sample_has_fan_and_row_mean_power(manifest):
    cfg, pred, l2 = make(manifest)
    ctl = Controls({c: 1.0 for c in manifest.cracs} | {"crac_02": 0.0}, {n: 6.0 if manifest.racks[n][0] == 1 else 8.0 for n in manifest.rack_names})
    l2.step(1.0, ctl)
    sample, ours, info = pred.calls[0]
    assert sample["fan"]["CRAC_02"] == 0.0 and sample["fan"]["CRAC_01"] == 1.0
    assert sample["row_power_kw"] == [6.0, 8.0]
    assert set(ours) == {rack_title(n) for n in manifest.rack_names}
    assert info == {"supply_m3s": 50.0, "aisle_leak_m3s": [1.0, 2.0]}


def test_only_temp_in_is_corrected_with_estimates(manifest):
    cfg, pred, l2 = make(manifest)
    ctl = Controls({c: 1.0 for c in manifest.cracs}, {n: 7.0 for n in manifest.rack_names})
    plain = FakeBase(manifest, cfg).step(1.0, ctl)
    out = l2.step(1.0, ctl)
    for n in manifest.rack_names:
        assert abs(out[f"{n}/temp_in"] - (plain[f"{n}/temp_in"] + 1.0)) < 1e-9
        assert out[f"{n}/temp_out"] == plain[f"{n}/temp_out"]
        e = l2.estimates[f"{n}/temp_in"]
        assert e["lower"] < out[f"{n}/temp_in"] < e["upper"] and e["confidence"] == "caution"
    assert all(k.endswith("/temp_in") for k in l2.estimates)


def test_fallback_keeps_base_values(manifest):
    cfg, pred, l2 = make(manifest, fallback=True)
    ctl = Controls({c: 1.0 for c in manifest.cracs}, {n: 7.0 for n in manifest.rack_names})
    plain = FakeBase(manifest, cfg).step(1.0, ctl)
    out = l2.step(1.0, ctl)
    assert all(abs(out[k] - plain[k]) < 1e-9 for k in plain)
    assert {e["confidence"] for e in l2.estimates.values()} == {"fallback"} and l2.fallback_steps == 1


def test_generator_attaches_estimates_to_temp_in_samples_only(manifest):
    cfg, pred, l2 = make(manifest)
    msgs = [m for m in Generator(manifest, get("normal"), l2, cfg, seed=1).run(3) if m["type"] == "sample"]
    for m in msgs:
        has = "confidence" in m
        assert has == m["topic"].endswith("/temp_in")
        if has:
            assert m["lower"] < m["upper"]


def test_mqtt_payload_includes_optional_fields_when_present():
    sent = []
    pub = object.__new__(MqttPublisher)
    pub.c = SimpleNamespace(publish=lambda topic, payload, qos, retain: sent.append(payload))
    pub.send({"type": "sample", "topic": "t", "ts": "x", "value": 1.0, "unit": "degC", "quality": "good", "lower": 0.5, "upper": 1.5, "confidence": "ok"})
    pub.send({"type": "sample", "topic": "t", "ts": "x", "value": 1.0, "unit": "degC", "quality": "good"})
    assert '"confidence":"ok"' in sent[0] and "confidence" not in sent[1]


def test_correction_changes_gradually_not_in_one_step(manifest):
    cfg = Config()
    l2 = L2Solver(manifest, cfg, base=FakeBase(manifest, cfg), predictor=JumpingPredictor())
    plain = FakeBase(manifest, cfg)
    racks = manifest.rack_names
    ok = Controls({c: 1.0 for c in manifest.cracs}, {n: 7.0 for n in racks})
    off = Controls({c: 1.0 for c in manifest.cracs} | {"crac_01": 0.0}, {n: 7.0 for n in racks})
    k = f"{racks[0]}/temp_in"
    l2.step(1.0, ok); plain.step(1.0, ok)
    first = l2.step(1.0, ok)[k] - plain.step(1.0, ok)[k]
    assert abs(first - 1.0) < 1e-6                              # 처음에는 목표 보정량에서 시작
    a = l2.step(1.0, off)[k] - plain.step(1.0, off)[k]
    assert 1.0 < a < 1.2                                       # 한 번에 +5로 뛰지 않는다
    for _ in range(600):
        b = l2.step(1.0, off)[k] - plain.step(1.0, off)[k]
    assert abs(b - 5.0) < 0.05                                 # 충분히 지나면 목표에 닿는다
    e = l2.estimates[k]
    assert abs((e["upper"] - e["lower"]) - 1.0) < 1e-6         # 구간 폭은 예측기가 낸 그대로
