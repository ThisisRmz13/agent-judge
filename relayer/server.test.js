const assert = require('node:assert/strict');
const http = require('node:http');
const test = require('node:test');

const { createApp } = require('./server');

function startServer(handler) {
  const server = http.createServer(handler);
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

function closeServer(server) {
  return new Promise((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()));
  });
}

async function requestQuote(baseUrl, pair = 'ETHUSDC') {
  const response = await fetch(
    `${baseUrl}/quote?pair=${encodeURIComponent(pair)}&reference=2478`
  );
  return { status: response.status, body: await response.json() };
}

function coinCapPayload(price, timestamp) {
  return JSON.stringify({ data: [String(price)], timestamp });
}

test('relayer maps the requested asset pair to CoinCap by base asset', async () => {
  let requestedPath = '';
  const now = Date.now();
  const upstream = await startServer((req, res) => {
    requestedPath = req.url;
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(coinCapPayload('2478', now));
  });
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/v3/price/bysymbol`;
  const app = createApp({ coinCapApiBase: upstreamUrl, apiKey: 'test-key', now: () => now });
  const relayer = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => relayer.once('listening', resolve));

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 200);
    assert.equal(requestedPath, '/v3/price/bysymbol/ETH');
    assert.equal(result.body.pair, 'ETHUSDC');
    assert.equal(result.body.source, 'coincap');
    assert.equal(result.body.price_x1e6, 2478000000);
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
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/v3/price/bysymbol`;
  const app = createApp({ coinCapApiBase: upstreamUrl, apiKey: 'test-key' });
  const relayer = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => relayer.once('listening', resolve));

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 502);
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
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/v3/price/bysymbol`;
  const app = createApp({ coinCapApiBase: upstreamUrl, apiKey: 'test-key' });
  const relayer = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => relayer.once('listening', resolve));

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 502);
    assert.match(result.body.error, /malformed JSON/);
  } finally {
    await closeServer(relayer);
    await closeServer(upstream);
  }
});

test('relayer rejects stale CoinCap quotes', async () => {
  const now = Date.now();
  const upstream = await startServer((_req, res) => {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(coinCapPayload('2478', now - 60001));
  });
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/v3/price/bysymbol`;
  const app = createApp({ coinCapApiBase: upstreamUrl, apiKey: 'test-key', now: () => now });
  const relayer = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => relayer.once('listening', resolve));

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 502);
    assert.match(result.body.error, /stale/);
  } finally {
    await closeServer(relayer);
    await closeServer(upstream);
  }
});

test('relayer rejects unsupported pairs', async () => {
  const app = createApp({ apiKey: 'test-key' });
  const relayer = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => relayer.once('listening', resolve));

  try {
    const response = await fetch(`http://127.0.0.1:${relayer.address().port}/quote?pair=NOTAPAIR`);
    const body = await response.json();
    assert.equal(response.status, 400);
    assert.match(body.error, /unsupported trading pair/);
  } finally {
    await closeServer(relayer);
  }
});

test('relayer requires the CoinCap API key', async () => {
  const app = createApp({ apiKey: '' });
  const relayer = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => relayer.once('listening', resolve));

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 500);
    assert.match(result.body.error, /COINCAP_API_KEY/);
  } finally {
    await closeServer(relayer);
  }
});
