const MODE = 'live';
const BINANCE_API_URL = 'https://data-api.binance.vision/api/v3/ticker/24hr';
const MAX_QUOTE_AGE_MS = 60000;

function normalizePair(pair) {
  const raw = String(pair || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (!raw) throw new Error('pair is required');
  return raw;
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' }
  });
}

async function handleQuote(request) {
  const url = new URL(request.url);
  const pair = url.searchParams.get('pair') || 'ETH/USDC';
  const reference = url.searchParams.get('reference') || '0';

  try {
    const requestedSymbol = normalizePair(pair);
    const response = await fetch(
      `${BINANCE_API_URL}?symbol=${encodeURIComponent(requestedSymbol)}`
    );

    if (!response.ok) {
      return json({ error: 'upstream quote provider returned an error', status: response.status }, 502);
    }

    let data;
    try {
      data = await response.json();
    } catch {
      return json({ error: 'upstream returned malformed JSON' }, 502);
    }

    if (!data || typeof data !== 'object') {
      return json({ error: 'upstream returned a malformed response' }, 502);
    }

    const returnedSymbol = normalizePair(data.symbol);
    if (returnedSymbol !== requestedSymbol) {
      return json({
        error: 'upstream returned a different trading pair',
        requested_pair: requestedSymbol,
        returned_pair: returnedSymbol
      }, 502);
    }

    const price = Number(data.lastPrice);
    const timestampMs = Number(data.closeTime);
    const now = Date.now();

    if (!Number.isFinite(price) || price <= 0) {
      return json({ error: 'upstream returned an invalid price' }, 502);
    }
    if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
      return json({ error: 'upstream returned an invalid quote timestamp' }, 502);
    }

    const ageMs = Math.max(0, now - timestampMs);
    if (ageMs > MAX_QUOTE_AGE_MS) {
      return json({
        error: 'upstream quote is stale',
        age_ms: ageMs,
        max_age_ms: MAX_QUOTE_AGE_MS
      }, 502);
    }

    return json({
      pair: data.symbol,
      reference,
      price_x1e6: Math.round(price * 1e6),
      timestamp_ms: timestampMs,
      age_ms: ageMs,
      fresh: true,
      source: 'binance-spot'
    });
  } catch (error) {
    return json({
      error: 'live quote request failed',
      detail: String(error.message || error)
    }, 502);
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === '/health') {
      return json({ ok: true, mode: MODE });
    }

    if (url.pathname === '/quote') {
      return handleQuote(request);
    }

    return new Response('Not Found', { status: 404 });
  }
};
