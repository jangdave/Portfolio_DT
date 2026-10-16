// REST와 WebSocket, 재생 시험(통합): 작은 .jsonl을 재생하면서 WebSocket 클라이언트가 같은 값을 받는지 확인한다.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import net from 'node:net';
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
    assert.equal(got[0].sensors.length, 2); // 접속 직후에는 아직 값이 없어도 모든 센서의 자리가 있다
    assert.ok(got[0].sensors.every((s) => s.value === null && s.quality === 'stale'));

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

const rawRequest = (port, bytes) => new Promise((resolve) => {
  const s = net.connect(port, '127.0.0.1', () => s.write(bytes));
  let data = '';
  s.on('data', (d) => (data += d.toString('latin1')));
  s.on('close', () => resolve(data));
  s.on('error', () => resolve(data));
  setTimeout(() => s.destroy(), 800);
});

test('이상한 요청 하나로 게이트웨이가 죽지 않는다(Host 헤더, 잘못된 WebSocket 프레임, 깨진 HTTP)', async () => {
  const gw = new Gateway(manifest);
  gw.on('log', () => {});
  const srv = createServer(gw, { port: 0 });
  const addr = await srv.listen();
  const dead = [];
  const onDie = (e) => dead.push(e);
  process.on('uncaughtException', onDie);
  try {
    // 1) 이상한 Host 헤더: 예외로 죽지 않고 정상 응답한다
    const r1 = await rawRequest(addr.port, 'GET /healthz HTTP/1.1\r\nHost: bad host\r\nConnection: close\r\n\r\n');
    assert.match(r1, /^HTTP\/1\.1 200/);
    // 2) 정상 업그레이드 뒤 RSV1 비트가 켜진 프레임
    const key = Buffer.from('0123456789abcdef').toString('base64');
    const up = `GET /ws HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: ${key}\r\nSec-WebSocket-Version: 13\r\n\r\n`;
    await new Promise((resolve) => {
      const s = net.connect(addr.port, '127.0.0.1', () => {
        s.write(up);
        setTimeout(() => {
          s.write(Buffer.from([0xc1, 0x80, 0, 0, 0, 0])); // RSV1, 마스크된 빈 페이로드
          setTimeout(() => { s.destroy(); resolve(); }, 150);
        }, 100);
      });
      s.on('error', () => resolve());
    });
    // 3) 깨진 HTTP
    await rawRequest(addr.port, 'THIS IS NOT HTTP\r\n\r\n');
    await new Promise((r) => setTimeout(r, 100));
    assert.deepEqual(dead, [], '처리되지 않은 예외로 프로세스가 죽을 뻔했다');
    // 4) 여전히 정상 동작한다
    assert.equal((await fetch(`http://127.0.0.1:${addr.port}/healthz`)).status, 200);
  } finally {
    process.off('uncaughtException', onDie);
    await srv.close();
  }
});
