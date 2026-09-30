const assert = require('node:assert/strict');
const http = require('node:http');
const test = require('node:test');

const { createApp } = require('./server');

const UPSTREAM_PATH = '/ticker';

function startServer(handler) {
  const server = http.createServer(handler);
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

function closeServer(server) {
  return new Promise((resolve, reject) => {
    if (typeof server.closeAllConnections === 'function') server.closeAllConnections();
    server.close((error) => (error ? reject(error) : resolve()));
  });
}

function startApp(options) {
  const app = createApp(options);
  const server = app.listen(0, '127.0.0.1');
  return new Promise((resolve) => server.once('listening', () => resolve(server)));
}

async function requestQuote(baseUrl, pair = 'ETHUSDC') {
  const response = await fetch(
    `${baseUrl}/quote?pair=${encodeURIComponent(pair)}&reference=2478`
  );
  return { status: response.status, body: await response.json() };
}

function upstreamUrl(upstream) {
  return `http://127.0.0.1:${upstream.address().port}${UPSTREAM_PATH}`;
}

function krakenPayload(price) {
  return JSON.stringify({
    error: [],
    result: { ETHUSDC: { c: [String(price), '0.100'] } }
  });
}

function jsonAt(res, dateMs, body) {
  res.sendDate = false;
  res.writeHead(200, {
    'content-type': 'application/json',
    date: new Date(dateMs).toUTCString()
  });
  res.end(body);
}

test('relayer sends the requested asset pair to Kraken as a pair', async () => {
  const now = Math.floor(Date.now() / 1000) * 1000;
  let requestedPath = '';
  const upstream = await startServer((req, res) => {
    requestedPath = req.url;
    jsonAt(res, now, krakenPayload('2478'));
  });
  const relayer = await startApp({ krakenApiBase: upstreamUrl(upstream), now: () => now });

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 200);
    assert.equal(requestedPath, '/ticker?pair=ETHUSDC');
    assert.equal(result.body.pair, 'ETHUSDC');
    assert.equal(result.body.source, 'kraken');
    assert.equal(result.body.price_x1e6, 2478000000);
    assert.equal(result.body.timestamp_ms, now);
    assert.equal(result.body.age_ms, 0);
    assert.equal(result.body.fresh, true);
  } finally {
    await closeServer(relayer);
    await closeServer(upstream);
  }
});

test('relayer rejects upstream HTTP failures', async () => {
  const upstream = await startServer((_req, res) => {
    res.writeHead(500, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: 'upstream down' }));
  });
  const relayer = await startApp({ krakenApiBase: upstreamUrl(upstream) });

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 502);
    assert.equal(result.body.status, 500);
    assert.match(result.body.error, /provider returned an error/);
  } finally {
    await closeServer(relayer);
    await closeServer(upstream);
  }
});

test('relayer rejects malformed upstream JSON', async () => {
  const upstream = await startServer((_req, res) => {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end('{not-json');
  });
  const relayer = await startApp({ krakenApiBase: upstreamUrl(upstream) });

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 502);
    assert.match(result.body.error, /malformed JSON/);
  } finally {
    await closeServer(relayer);
    await closeServer(upstream);
  }
});

test('relayer rejects stale Kraken quotes', async () => {
  const now = Math.floor(Date.now() / 1000) * 1000;
  const upstream = await startServer((_req, res) => {
    jsonAt(res, now - 60001, krakenPayload('2478'));
  });
  const relayer = await startApp({ krakenApiBase: upstreamUrl(upstream), now: () => now });

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 502);
    assert.match(result.body.error, /stale/);
    assert.ok(result.body.age_ms > result.body.max_age_ms);
  } finally {
    await closeServer(relayer);
    await closeServer(upstream);
  }
});

test('relayer rejects unsupported pairs', async () => {
  const relayer = await startApp({});

  try {
    const response = await fetch(
      `http://127.0.0.1:${relayer.address().port}/quote?pair=NOTAPAIR`
    );
    const body = await response.json();
    assert.equal(response.status, 400);
    assert.match(body.error, /unsupported trading pair/);
  } finally {
    await closeServer(relayer);
  }
});

test('relayer rejects quotes that carry no timestamp', async () => {
  const upstream = await startServer((_req, res) => {
    res.sendDate = false;
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(krakenPayload('2478'));
  });
  const relayer = await startApp({ krakenApiBase: upstreamUrl(upstream) });

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 502);
    assert.match(result.body.error, /invalid quote timestamp/);
  } finally {
    await closeServer(relayer);
    await closeServer(upstream);
  }
});
