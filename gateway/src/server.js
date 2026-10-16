// HTTP(REST)와 WebSocket 서버 (docs/11 4.3, 4.5장). 개발 중에는 127.0.0.1에서만 연다(8장).
// 이상한 요청 하나로 프로세스가 죽지 않게 한다: Host 헤더를 쓰지 않고, 잘못된 WebSocket 프레임의 오류를 접속마다 받아서 끊는다.
import http from 'node:http';
import { WebSocketServer } from 'ws';

const MAX_BUFFERED = 1 << 20; // 이만큼 쌓이도록 못 받는 클라이언트는 끊는다(메모리가 계속 늘지 않게)

export function createServer(gateway, { host = '127.0.0.1', port = 8080 } = {}) {
  const started = Date.now();
  const json = (res, status, body) => {
    res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify(body));
  };

  const server = http.createServer((req, res) => {
    let url;
    try {
      url = new URL(req.url, 'http://localhost'); // Host 헤더는 쓰지 않는다(이상한 값이면 예외가 난다)
    } catch {
      return json(res, 400, { error: '주소가 올바르지 않다' });
    }
    if (req.method !== 'GET') return json(res, 405, { error: 'GET만 지원한다' });
    switch (url.pathname) {
      case '/healthz':
        return json(res, 200, { ok: true, uptimeSeconds: Math.round((Date.now() - started) / 1000), sensors: gateway.latest.size, dropped: gateway.dropped, clients: wss.clients.size });
      case '/api/sensors':
        return json(res, 200, gateway.manifest);
      case '/api/latest':
        return json(res, 200, gateway.snapshot());
      case '/api/aggregates':
        return json(res, 200, gateway.aggregates);
      case '/api/history': {
        const id = url.searchParams.get('sensorId');
        if (!id) return json(res, 400, { error: 'sensorId가 필요하다' });
        const minutes = Number(url.searchParams.get('minutes') ?? gateway.cfg.historyMinutes);
        if (!Number.isFinite(minutes) || minutes <= 0) return json(res, 400, { error: 'minutes가 올바르지 않다' });
        const h = gateway.historyOf(id, minutes);
        return h ? json(res, 200, { sensorId: id, samples: h }) : json(res, 404, { error: `센서가 없다: ${id}` });
      }
      default:
        return json(res, 404, { error: '없는 주소' });
    }
  });
  server.on('clientError', (_err, socket) => socket.destroy()); // 깨진 HTTP 요청은 조용히 끊는다

  const wss = new WebSocketServer({ server, path: '/ws', maxPayload: 4096 }); // 클라이언트가 보내는 메시지는 쓰지 않으므로 작게
  wss.on('error', (err) => gateway.log(`WebSocket 서버 오류: ${err.message}`));
  const broadcast = (msg) => {
    const text = JSON.stringify(msg);
    for (const c of wss.clients) {
      if (c.readyState !== 1) continue;
      if (c.bufferedAmount > MAX_BUFFERED) {
        c.terminate();
        continue;
      }
      c.send(text);
    }
  };
  wss.on('connection', (ws) => {
    ws.on('error', (err) => {
      gateway.log(`WebSocket 접속 오류(끊음): ${err.message}`);
      ws.terminate();
    });
    ws.send(JSON.stringify(gateway.snapshot()));
  });
  for (const ev of ['sample', 'alarm', 'scenario', 'aggregate']) gateway.on(ev, broadcast);

  return {
    server,
    wss,
    listen: () => new Promise((resolve) => server.listen(port, host, () => resolve(server.address()))),
    close: () => new Promise((resolve) => {
      for (const c of wss.clients) c.terminate();
      wss.close(() => server.close(() => resolve()));
    }),
  };
}
