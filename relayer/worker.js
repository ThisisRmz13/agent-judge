const MODE = 'live';
const COINBASE_TICKER_URL = 'https://api.exchange.coinbase.com/products';
const MAX_QUOTE_AGE_MS = 60000;

function normalizePair(pair) {
  const raw = String(pair || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (!raw) throw new Error('pair is required');
  return raw;
}

function toCoinbaseProductId(symbol) {
  const knownQuotes = ['USDC', 'USDT', 'USD', 'EUR', 'GBP', 'BTC', 'ETH'];
  for (const quote of knownQuotes) {
    if (symbol.endsWith(quote) && symbol.length > quote.length) {
      return `${symbol.slice(0, -quote.length)}-${quote}`;
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

async function handleQuote(request) {
  const url = new URL(request.url);
  const pair = url.searchParams.get('pair') || 'ETH/USDC';
  const reference = url.searchParams.get('reference') || '0';

  try {
    const requestedSymbol = normalizePair(pair);
    const productId = toCoinbaseProductId(requestedSymbol);
    const response = await fetch(
      `${COINBASE_TICKER_URL}/${encodeURIComponent(productId)}/ticker`,
      { headers: { 'accept': 'application/json' } }
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

    const returnedProduct = normalizePair(productId.replace('-', ''));
    if (returnedProduct !== requestedSymbol) {
      return json({
        error: 'upstream returned a different trading pair',
        requested_pair: requestedSymbol,
        returned_pair: returnedProduct
      }, 502);
    }

    const price = Number(data.price);
    const timestampMs = Date.parse(data.time);
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
      pair: requestedSymbol,
      reference,
      price_x1e6: Math.round(price * 1e6),
      timestamp_ms: timestampMs,
      age_ms: ageMs,
      fresh: true,
      source: 'coinbase-spot'
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
