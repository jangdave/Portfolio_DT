// 입력: .jsonl 재생(MQTT 없이도 같은 값을 재생, docs/11 5장)과 MQTT 구독(선택).
import fs from 'node:fs';
import readline from 'node:readline';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 생성기가 만든 .jsonl을 센서 시각 간격에 맞춰 재생한다. timeScale=0이면 기다리지 않는다.
export async function replayFile(gateway, file, { timeScale = 1, signal } = {}) {
  const rl = readline.createInterface({ input: fs.createReadStream(file, { encoding: 'utf8' }), crlfDelay: Infinity });
  let lastTs = null;
  let count = 0;
  for await (const line of rl) {
    if (signal?.aborted) break;
    if (!line.trim()) continue;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      gateway.log(`재생: JSON이 아닌 줄을 건너뜀: ${line.slice(0, 60)}`);
      continue;
    }
    if (msg.type === 'scenario') {
      gateway.scenarioEvent(msg);
      continue;
    }
    if (msg.type !== 'sample') continue; // 알람, 집계는 게이트웨이가 다시 계산한다
    const t = Date.parse(msg.ts);
    if (timeScale > 0 && lastTs != null && t > lastTs) await sleep((t - lastTs) / timeScale);
    if (lastTs == null || t > lastTs) lastTs = t;
    gateway.ingest(msg);
    count += 1;
  }
  gateway.flush(); // 마지막 시각의 집계를 확정한다
  return count;
}

// MQTT 구독(선택). mqtt 패키지가 있어야 한다. 브로커는 이 저장소가 설치하지 않는다.
export async function connectMqtt(gateway, url) {
  let mqtt;
  try {
    mqtt = (await import('mqtt')).default;
  } catch {
    throw new Error('mqtt 패키지가 없다. gateway 폴더에서 `npm install mqtt`를 실행한다');
  }
  const client = mqtt.connect(url);
  client.on('connect', () => {
    client.subscribe('dct/v1/#', { qos: 0 });
    gateway.log(`MQTT 연결: ${url}`);
  });
  client.on('message', (topic, payload) => gateway.ingestMqtt(topic, payload));
  client.on('error', (err) => gateway.log(`MQTT 오류: ${err.message}`));
  return client;
}
