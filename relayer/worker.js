const MODE = 'live';
const COINCAP_API_BASE = 'https://rest.coincap.io/v3/price/bysymbol';
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

async function handleQuote(request, env) {
  const url = new URL(request.url);
  const pair = url.searchParams.get('pair') || 'ETHUSDC';
  const reference = url.searchParams.get('reference') || '0';

  try {
    const requestedSymbol = normalizePair(pair);
    const asset = baseAsset(requestedSymbol);
    const apiKey = env?.COINCAP_API_KEY;
    if (!apiKey) {
      return json({ error: 'COINCAP_API_KEY secret is not configured' }, 500);
    }

    const response = await fetch(`${COINCAP_API_BASE}/${encodeURIComponent(asset)}`, {
      headers: {
        accept: 'application/json',
        Authorization: `Bearer ${apiKey}`
      }
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

    const data = payload?.data;
    if (!Array.isArray(data) || data.length === 0) {
      return json({ error: 'upstream returned a malformed response' }, 502);
    }

    const price = Number(data[0]);
    const timestampMs = Number(payload.timestamp);
    const now = Date.now();

    if (!Number.isFinite(price) || price <= 0) {
      return json({ error: 'upstream returned an invalid price' }, 502);
    }
    if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
      return json({ error: 'upstream returned an invalid quote timestamp' }, 502);
    }

    const ageMs = Math.max(0, now - timestampMs);
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
      source: 'coincap'
    });
  } catch (error) {
    return json({ error: 'live quote request failed', detail: String(error.message || error) }, 502);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/health') return json({ ok: true, mode: MODE, source: 'coincap' });
    if (url.pathname === '/quote') return handleQuote(request, env);
    return new Response('Not Found', { status: 404 });
  }
};
