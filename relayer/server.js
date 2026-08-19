const express = require('express');
const app = express();
app.use(express.json());

const PORT = Number(process.env.PORT || 8787);
const MODE = process.env.QUOTE_MODE || 'mock';
const BINANCE_API_URL = process.env.BINANCE_API_URL || 'https://api.binance.com/api/v3/ticker/24hr';
const MOCK_PRICE_X1E6 = Number(process.env.MOCK_PRICE_X1E6 || 3200000000);
const MAX_QUOTE_AGE_MS = Number(process.env.MAX_QUOTE_AGE_MS || 60000);

function json(res, status, body) {
  res.status(status).type('application/json').send(JSON.stringify(body));
}

function normalizePair(pair) {
  const raw = String(pair || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (!raw) throw new Error('pair is required');
  return raw;
}

app.get('/health', (_req, res) => json(res, 200, { ok: true, mode: MODE }));

app.get('/quote', async (req, res) => {
  const pair = String(req.query.pair || 'ETH/USDC');
  const reference = String(req.query.reference || '0');

  if (MODE === 'mock') {
    return json(res, 200, {
      pair,
      reference,
      price_x1e6: MOCK_PRICE_X1E6,
      timestamp_ms: Date.now(),
      age_ms: 0,
      fresh: true,
      source: 'mock'
    });
  }

  try {
    const symbol = normalizePair(pair);
    const response = await fetch(`${BINANCE_API_URL}?symbol=${encodeURIComponent(symbol)}`);
    if (!response.ok) {
      return json(res, 502, { error: 'upstream quote provider returned an error', status: response.status });
    }

    const data = await response.json();
    const price = Number(data.lastPrice);
    const timestampMs = Number(data.closeTime);
    if (!Number.isFinite(price) || price <= 0) {
      return json(res, 502, { error: 'upstream returned an invalid price' });
    }
    if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
      return json(res, 502, { error: 'upstream returned an invalid quote timestamp' });
    }

    const ageMs = Math.max(0, Date.now() - timestampMs);
    if (ageMs > MAX_QUOTE_AGE_MS) {
      return json(res, 502, {
        error: 'upstream quote is stale',
        age_ms: ageMs,
        max_age_ms: MAX_QUOTE_AGE_MS
      });
    }

    return json(res, 200, {
      pair,
      reference,
      price_x1e6: Math.round(price * 1e6),
      timestamp_ms: timestampMs,
      age_ms: ageMs,
      fresh: true,
      source: 'binance-spot'
    });
  } catch (error) {
    return json(res, 502, { error: 'live quote request failed', detail: String(error.message || error) });
  }
});

app.listen(PORT, '0.0.0.0', () => console.log(`Agent Judge relayer listening on :${PORT} (${MODE})`));
