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

async function requestQuote(baseUrl, pair = 'ETH/USDC') {
  const response = await fetch(
    `${baseUrl}/quote?pair=${encodeURIComponent(pair)}&reference=1906.94`
  );
  return { status: response.status, body: await response.json() };
}

test('relayer binds returned Binance symbol to requested pair', async () => {
  const upstream = await startServer((_req, res) => {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({
      symbol: 'BTCUSDC',
      lastPrice: '60000',
      closeTime: Date.now()
    }));
  });
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/ticker`;
  const app = createApp({ mode: 'live', binanceApiUrl: upstreamUrl });
  const relayer = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => relayer.once('listening', resolve));

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 502);
    assert.match(result.body.error, /different trading pair/);
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
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/ticker`;
  const app = createApp({ mode: 'live', binanceApiUrl: upstreamUrl });
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
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/ticker`;
  const app = createApp({ mode: 'live', binanceApiUrl: upstreamUrl });
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

test('relayer rejects stale upstream quotes', async () => {
  const upstream = await startServer((_req, res) => {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({
      symbol: 'ETHUSDC',
      lastPrice: '1906.94',
      closeTime: Date.now() - 60001
    }));
  });
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/ticker`;
  const app = createApp({ mode: 'live', binanceApiUrl: upstreamUrl, maxQuoteAgeMs: 60000 });
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

test('relayer accepts a fresh correctly bound quote', async () => {
  const now = Date.now();
  const upstream = await startServer((_req, res) => {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({
      symbol: 'ETHUSDC',
      lastPrice: '1906.94',
      closeTime: now
    }));
  });
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/ticker`;
  const app = createApp({ mode: 'live', binanceApiUrl: upstreamUrl, now: () => now });
  const relayer = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => relayer.once('listening', resolve));

  try {
    const result = await requestQuote(`http://127.0.0.1:${relayer.address().port}`);
    assert.equal(result.status, 200);
    assert.equal(result.body.pair, 'ETHUSDC');
    assert.equal(result.body.source, 'binance-spot');
    assert.equal(result.body.fresh, true);
    assert.equal(result.body.price_x1e6, 1906940000);
  } finally {
    await closeServer(relayer);
    await closeServer(upstream);
  }
});
