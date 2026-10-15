// REST와 WebSocket, 재생 시험(통합): 작은 .jsonl을 재생하면서 WebSocket 클라이언트가 같은 값을 받는지 확인한다.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { Gateway } from '../src/core.js';
import { replayFile } from '../src/inputs.js';
import { createServer } from '../src/server.js';

const manifest = {
  version: 1,
  hall: 'hall01',
  sensors: [
    { sensorId: 'H01-RK01-TEMP-IN', topic: 'dct/v1/hall01/rack_01/temp_in', equipmentPath: '/DC/Hall01/Row01/Rack_01', equipmentType: 'rack', metric: 'temp_in', unit: 'degC', range: [10, 45], warn: 27, critical: 32 },
    { sensorId: 'H01-RK01-POWER', topic: 'dct/v1/hall01/rack_01/power', equipmentPath: '/DC/Hall01/Row01/Rack_01', equipmentType: 'rack', metric: 'power', unit: 'kW', range: [0, 15], warn: 10, critical: 13 },
  ],
};
const T0 = Date.parse('2026-10-15T09:00:00.000Z');
const ts = (s) => new Date(T0 + s * 1000).toISOString();

function writeReplay() {
  const lines = [{ type: 'scenario', event: 'start', name: 'demo', ts: ts(0) }];
  const temps = [24, 24, 28, 28, 28, 28];
  temps.forEach((v, s) => {
    lines.push({ type: 'sample', sensorId: 'H01-RK01-TEMP-IN', topic: manifest.sensors[0].topic, ts: ts(s), value: v, unit: 'degC', quality: 'good' });
    lines.push({ type: 'sample', sensorId: 'H01-RK01-POWER', topic: manifest.sensors[1].topic, ts: ts(s), value: 7, unit: 'kW', quality: 'good' });
  });
  lines.push({ type: 'alarm', sensorId: 'X', from: 'normal', to: 'warn', value: 1, ts: ts(1) }); // 재생에서는 무시하고 게이트웨이가 다시 계산한다
  lines.push({ type: 'scenario', event: 'end', name: 'demo', ts: ts(6) });
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'dct-gw-')), 'r.jsonl');
  fs.writeFileSync(f, lines.map((l) => JSON.stringify(l)).join('\n') + '\nnot json\n');
  return f;
}

const waitFor = async (cond, ms = 3000) => {
  const t0 = Date.now();
  while (!cond()) {
    if (Date.now() - t0 > ms) throw new Error('기다리던 조건이 시간 안에 되지 않았다');
    await new Promise((r) => setTimeout(r, 10));
  }
};

test('재생하면 WebSocket으로 snapshot, sample, alarm, scenario가 온다', async () => {
  const gw = new Gateway(manifest);
  gw.on('log', () => {});
  const srv = createServer(gw, { port: 0 });
  const addr = await srv.listen();
  const base = `http://127.0.0.1:${addr.port}`;
  try {
    const got = [];
    const ws = new WebSocket(`ws://127.0.0.1:${addr.port}/ws`);
    ws.onmessage = (e) => got.push(JSON.parse(e.data));
    await waitFor(() => got.length >= 1);
    assert.equal(got[0].type, 'snapshot');
    assert.deepEqual(got[0].sensors, []); // 접속 직후에는 아직 값이 없다

    const n = await replayFile(gw, writeReplay(), { timeScale: 0 });
    assert.equal(n, 12);
    await waitFor(() => got.some((m) => m.type === 'scenario' && m.event === 'end'));
    assert.equal(got.filter((m) => m.type === 'sample').length >= 12, true);
    const alarms = got.filter((m) => m.type === 'alarm');
    assert.deepEqual(alarms.map((a) => [a.sensorId, a.from, a.to]), [['H01-RK01-TEMP-IN', 'normal', 'warn']]);
    assert.ok(got.some((m) => m.type === 'aggregate' && m.name === 'it_power'));
    ws.close();

    // 나중에 접속하면 snapshot에 최근 값과 알람 상태가 들어 있다
    const late = [];
    const ws2 = new WebSocket(`ws://127.0.0.1:${addr.port}/ws`);
    ws2.onmessage = (e) => late.push(JSON.parse(e.data));
    await waitFor(() => late.length >= 1);
    const snap = late[0];
    assert.equal(snap.sensors.find((s) => s.sensorId === 'H01-RK01-TEMP-IN').alarm, 'warn');
    ws2.close();

    // REST
    const health = await (await fetch(`${base}/healthz`)).json();
    assert.equal(health.ok, true);
    assert.equal(health.sensors, 2);
    assert.equal((await (await fetch(`${base}/api/sensors`)).json()).sensors.length, 2);
    const latest = await (await fetch(`${base}/api/latest`)).json();
    assert.equal(latest.sensors.length, 2);
    const hist = await (await fetch(`${base}/api/history?sensorId=H01-RK01-TEMP-IN&minutes=15`)).json();
    assert.equal(hist.samples.length, 6);
    assert.equal((await fetch(`${base}/api/history`)).status, 400);
    assert.equal((await fetch(`${base}/api/history?sensorId=없음`)).status, 404);
    assert.equal((await fetch(`${base}/nope`)).status, 404);
    assert.ok((await (await fetch(`${base}/api/aggregates`)).json()).pue);
  } finally {
    await srv.close();
  }
});

test('같은 .jsonl을 두 번 재생하면 같은 알람이 나온다(재현)', async () => {
  const file = writeReplay();
  const run = async () => {
    const gw = new Gateway(manifest);
    gw.on('log', () => {});
    const alarms = [];
    gw.on('alarm', (a) => alarms.push([a.sensorId, a.from, a.to, a.ts]));
    await replayFile(gw, file, { timeScale: 0 });
    return alarms;
  };
  assert.deepEqual(await run(), await run());
});
