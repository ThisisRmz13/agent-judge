const express = require('express');

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

function createApp({
  mode = MODE,
  binanceApiUrl = BINANCE_API_URL,
  mockPriceX1e6 = MOCK_PRICE_X1E6,
  maxQuoteAgeMs = MAX_QUOTE_AGE_MS,
  fetchImpl = fetch,
  now = () => Date.now()
} = {}) {
  const app = express();
  app.use(express.json());

  app.get('/health', (_req, res) => json(res, 200, { ok: true, mode }));

  app.get('/quote', async (req, res) => {
    const pair = String(req.query.pair || 'ETH/USDC');
    const reference = String(req.query.reference || '0');

    if (mode === 'mock') {
      return json(res, 200, {
        pair,
        reference,
        price_x1e6: mockPriceX1e6,
        timestamp_ms: now(),
        age_ms: 0,
        fresh: true,
        source: 'mock'
      });
    }

    try {
      const requestedSymbol = normalizePair(pair);
      const response = await fetchImpl(
        `${binanceApiUrl}?symbol=${encodeURIComponent(requestedSymbol)}`
      );
      if (!response.ok) {
        return json(res, 502, {
          error: 'upstream quote provider returned an error',
          status: response.status
        });
      }

      let data;
      try {
        data = await response.json();
      } catch (_error) {
        return json(res, 502, { error: 'upstream returned malformed JSON' });
      }

      if (!data || typeof data !== 'object') {
        return json(res, 502, { error: 'upstream returned a malformed response' });
      }

      const returnedSymbol = normalizePair(data.symbol);
      if (returnedSymbol !== requestedSymbol) {
        return json(res, 502, {
          error: 'upstream returned a different trading pair',
          requested_pair: requestedSymbol,
          returned_pair: returnedSymbol
        });
      }

      const price = Number(data.lastPrice);
      const timestampMs = Number(data.closeTime);
      if (!Number.isFinite(price) || price <= 0) {
        return json(res, 502, { error: 'upstream returned an invalid price' });
      }
      if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
        return json(res, 502, { error: 'upstream returned an invalid quote timestamp' });
      }

      const ageMs = Math.max(0, now() - timestampMs);
      if (ageMs > maxQuoteAgeMs) {
        return json(res, 502, {
          error: 'upstream quote is stale',
          age_ms: ageMs,
          max_age_ms: maxQuoteAgeMs
        });
      }

      return json(res, 200, {
        pair: data.symbol,
        reference,
        price_x1e6: Math.round(price * 1e6),
        timestamp_ms: timestampMs,
        age_ms: ageMs,
        fresh: true,
        source: 'binance-spot'
      });
    } catch (error) {
      return json(res, 502, {
        error: 'live quote request failed',
        detail: String(error.message || error)
      });
    }
  });

  return app;
}

if (require.main === module) {
  createApp().listen(PORT, '0.0.0.0', () =>
    console.log(`Agent Judge relayer listening on :${PORT} (${MODE})`)
  );
}

module.exports = { createApp, normalizePair };
