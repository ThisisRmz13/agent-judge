const express = require('express');
const app = express();
app.use(express.json());

const PORT = Number(process.env.PORT || 8787);
const MODE = process.env.QUOTE_MODE || 'mock';
const BINANCE_API_URL = process.env.BINANCE_API_URL || 'https://api.binance.com/api/v3/ticker/price';
const MOCK_PRICE_X1E6 = Number(process.env.MOCK_PRICE_X1E6 || 3200000000);

function json(res, status, body) {
  res.status(status).type('application/json').send(JSON.stringify(body));
}

function normalizePair(pair) {
  const raw = String(pair || 'ETH/USDC').toUpperCase().replace(/[^A-Z0-9]/g, '');
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
    const price = Number(data.price);
    if (!Number.isFinite(price) || price <= 0) {
      return json(res, 502, { error: 'upstream returned an invalid price' });
    }
    return json(res, 200, {
      pair,
      reference,
      price_x1e6: Math.round(price * 1e6),
      source: 'binance-spot'
    });
  } catch (error) {
    return json(res, 502, { error: 'live quote request failed', detail: String(error.message || error) });
  }
});

app.listen(PORT, () => console.log(`Agent Judge relayer listening on :${PORT} (${MODE})`));
