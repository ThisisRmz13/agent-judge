const express = require('express');

const PORT = Number(process.env.PORT || 8787);
const KRAKEN_API_BASE = process.env.KRAKEN_API_BASE || 'https://api.kraken.com/0/public/Ticker';
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

function quoteTimestampMs(response) {
  const header = response.headers.get('date');
  if (!header) return NaN;
  return Date.parse(header);
}

function readPrice(payload, symbol) {
  const ticker = payload?.result?.[symbol] || Object.values(payload?.result || {})[0];
  return Number(ticker?.c?.[0]);
}

function createApp({
  krakenApiBase = KRAKEN_API_BASE,
  maxQuoteAgeMs = MAX_QUOTE_AGE_MS,
  fetchImpl = fetch,
  now = () => Date.now()
} = {}) {
  const app = express();
  app.use(express.json());

  app.get('/health', (_req, res) => json(res, 200, { ok: true, mode: 'live', source: 'kraken' }));

  app.get('/quote', async (req, res) => {
    const pair = String(req.query.pair || 'ETHUSDC');
    const reference = String(req.query.reference || '0');

    let requestedSymbol;
    try {
      requestedSymbol = normalizePair(pair);
      baseAsset(requestedSymbol);
    } catch (error) {
      return json(res, 400, { error: String(error.message || error) });
    }

    try {
      const response = await fetchImpl(
        `${krakenApiBase}?pair=${encodeURIComponent(requestedSymbol)}`,
        { headers: { accept: 'application/json' } }
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

      if (Array.isArray(payload?.error) && payload.error.length > 0) {
        return json(res, 502, {
          error: 'upstream quote provider returned an error',
          detail: payload.error.join(' | ')
        });
      }

      const price = readPrice(payload, requestedSymbol);
      if (!Number.isFinite(price) || price <= 0) {
        return json(res, 502, { error: 'upstream returned an invalid price' });
      }

      const timestampMs = quoteTimestampMs(response);
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
        source: 'kraken'
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
    console.log(`Agent Judge Kraken relayer listening on :${PORT}`)
  );
}

module.exports = { createApp, normalizePair, baseAsset };
