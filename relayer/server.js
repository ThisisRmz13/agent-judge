const express = require('express');

const PORT = Number(process.env.PORT || 8787);
const COINCAP_API_BASE = process.env.COINCAP_API_BASE || 'https://rest.coincap.io/v3/price/bysymbol';
const MAX_QUOTE_AGE_MS = Number(process.env.MAX_QUOTE_AGE_MS || 60000);

function json(res, status, body) {
  res.status(status).type('application/json').send(JSON.stringify(body));
}

function normalizePair(pair) {
  const raw = String(pair || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (!raw) throw new Error('pair is required');
  return raw;
}

function baseAsset(pair) {
  const normalized = normalizePair(pair);
  for (const quote of ['USDC', 'USDT', 'USD']) {
    if (normalized.endsWith(quote) && normalized.length > quote.length) {
      return normalized.slice(0, -quote.length);
    }
  }
  throw new Error('unsupported trading pair');
}

function createApp({
  coinCapApiBase = COINCAP_API_BASE,
  maxQuoteAgeMs = MAX_QUOTE_AGE_MS,
  apiKey = process.env.COINCAP_API_KEY,
  fetchImpl = fetch,
  now = () => Date.now()
} = {}) {
  const app = express();
  app.use(express.json());

  app.get('/health', (_req, res) => json(res, 200, { ok: true, mode: 'live', source: 'coincap' }));

  app.get('/quote', async (req, res) => {
    const pair = String(req.query.pair || 'ETHUSDC');
    const reference = String(req.query.reference || '0');

    if (!apiKey) {
      return json(res, 500, { error: 'COINCAP_API_KEY secret is not configured' });
    }

    let requestedSymbol;
    let asset;
    try {
      requestedSymbol = normalizePair(pair);
      asset = baseAsset(requestedSymbol);
    } catch (error) {
      return json(res, 400, { error: String(error.message || error) });
    }

    try {
      const response = await fetchImpl(
        `${coinCapApiBase}/${encodeURIComponent(asset)}`,
        { headers: { accept: 'application/json', Authorization: `Bearer ${apiKey}` } }
      );

      if (!response.ok) {
        return json(res, 502, {
          error: 'upstream quote provider returned an error',
          status: response.status
        });
      }

      let payload;
      try {
        payload = await response.json();
      } catch (_error) {
        return json(res, 502, { error: 'upstream returned malformed JSON' });
      }

      const data = payload?.data;
      if (!Array.isArray(data) || data.length === 0) {
        return json(res, 502, { error: 'upstream returned a malformed response' });
      }

      const price = Number(data[0]);
      const timestampMs = Number(payload.timestamp);
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
        pair: requestedSymbol,
        reference,
        price_x1e6: Math.round(price * 1e6),
        timestamp_ms: timestampMs,
        age_ms: ageMs,
        fresh: true,
        source: 'coincap'
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
    console.log(`Agent Judge CoinCap relayer listening on :${PORT}`)
  );
}

module.exports = { createApp, normalizePair, baseAsset };
