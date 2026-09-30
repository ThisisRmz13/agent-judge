const MODE = 'live';
const KRAKEN_API_BASE = 'https://api.kraken.com/0/public/Ticker';
const MAX_QUOTE_AGE_MS = 60000;

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

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' }
  });
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

async function handleQuote(request) {
  const url = new URL(request.url);
  const pair = url.searchParams.get('pair') || 'ETHUSDC';
  const reference = url.searchParams.get('reference') || '0';

  let requestedSymbol;
  try {
    requestedSymbol = normalizePair(pair);
    baseAsset(requestedSymbol);
  } catch (error) {
    return json({ error: String(error.message || error) }, 400);
  }

  try {
    const response = await fetch(`${KRAKEN_API_BASE}?pair=${encodeURIComponent(requestedSymbol)}`, {
      headers: { accept: 'application/json' }
    });

    if (!response.ok) {
      return json({ error: 'upstream quote provider returned an error', status: response.status }, 502);
    }

    let payload;
    try {
      payload = await response.json();
    } catch {
      return json({ error: 'upstream returned malformed JSON' }, 502);
    }

    if (Array.isArray(payload?.error) && payload.error.length > 0) {
      return json({ error: 'upstream quote provider returned an error', detail: payload.error.join(' | ') }, 502);
    }

    const price = readPrice(payload, requestedSymbol);
    if (!Number.isFinite(price) || price <= 0) {
      return json({ error: 'upstream returned an invalid price' }, 502);
    }

    const timestampMs = quoteTimestampMs(response);
    if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
      return json({ error: 'upstream returned an invalid quote timestamp' }, 502);
    }

    const ageMs = Math.max(0, Date.now() - timestampMs);
    if (ageMs > MAX_QUOTE_AGE_MS) {
      return json({ error: 'upstream quote is stale', age_ms: ageMs, max_age_ms: MAX_QUOTE_AGE_MS }, 502);
    }

    return json({
      pair: requestedSymbol,
      reference,
      price_x1e6: Math.round(price * 1e6),
      timestamp_ms: timestampMs,
      age_ms: ageMs,
      fresh: true,
      source: 'kraken'
    });
  } catch (error) {
    return json({ error: 'live quote request failed', detail: String(error.message || error) }, 502);
  }
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === '/health') return json({ ok: true, mode: MODE, source: 'kraken' });
    if (url.pathname === '/quote') return handleQuote(request);
    return new Response('Not Found', { status: 404 });
  }
};
