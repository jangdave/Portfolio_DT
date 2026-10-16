// 게이트웨이 실행.
//   node src/index.js --manifest ../sim/out/sensor_manifest.json --replay ../sim/out/recordings/cooling_failure.jsonl --time-scale 10
//   node src/index.js --manifest ../sim/out/sensor_manifest.json --mqtt mqtt://127.0.0.1:1883 --record ../sim/out/recordings/live.jsonl
//
// 입력은 --replay(.jsonl 재생, MQTT 없이도 같은 값) 또는 --mqtt(브로커 주소) 중 하나 이상을 쓴다.
// 밖에는 REST(/healthz, /api/sensors, /api/latest, /api/history, /api/aggregates)와 WebSocket(/ws)을 연다. 기본은 127.0.0.1만.
import fs from 'node:fs';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { Gateway } from './core.js';
import { connectMqtt, replayFile } from './inputs.js';
import { createServer } from './server.js';

const { values: a } = parseArgs({
  options: {
    manifest: { type: 'string' },
    replay: { type: 'string' },
    mqtt: { type: 'string' },
    record: { type: 'string' },
    port: { type: 'string', default: '8080' },
    host: { type: 'string', default: '127.0.0.1' },
    'time-scale': { type: 'string', default: '1' },
    loop: { type: 'boolean', default: false },
  },
});

if (!a.manifest || (!a.replay && !a.mqtt)) {
  console.error('사용: node src/index.js --manifest <매니페스트.json> (--replay <파일.jsonl> | --mqtt <mqtt://호스트:포트>) [--record 파일] [--port 8080] [--time-scale 1] [--loop]');
  process.exit(2);
}

const manifest = JSON.parse(fs.readFileSync(a.manifest, 'utf8'));
const gateway = new Gateway(manifest);
gateway.on('log', (m) => console.error(`[게이트웨이] ${m}`));

if (a.record) {
  fs.mkdirSync(path.dirname(path.resolve(a.record)), { recursive: true });
  const out = fs.createWriteStream(a.record, { flags: 'w' });
  for (const ev of ['sample', 'alarm', 'scenario', 'aggregate']) gateway.on(ev, (m) => out.write(JSON.stringify(m) + '\n'));
}

const srv = createServer(gateway, { host: a.host, port: Number(a.port) });
const addr = await srv.listen();
console.error(`[게이트웨이] http://${addr.address}:${addr.port} (WebSocket /ws), 센서 ${manifest.sensors.length}개`);

if (a.mqtt) {
  await connectMqtt(gateway, a.mqtt);
  // 모든 센서가 동시에 끊겨도 stale을 알리도록 수신 시각만큼 시계를 민다(재생은 센서 시각 기준이라 쓰지 않는다)
  setInterval(() => gateway.heartbeat(), 1000).unref();
}
if (a.replay) {
  const ts = Number(a['time-scale']);
  do {
    const n = await replayFile(gateway, a.replay, { timeScale: ts });
    console.error(`[게이트웨이] 재생 끝: 샘플 ${n}건, 알람 상태 ${[...gateway.latest.values()].filter((e) => e.alarm !== 'normal').length}개 센서`);
  } while (a.loop);
}
process.on('SIGINT', async () => {
  await srv.close();
  process.exit(0);
});
