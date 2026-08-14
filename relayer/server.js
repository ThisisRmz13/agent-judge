const express = require('express');
const app = express();
app.use(express.json());

const PORT = Number(process.env.PORT || 8787);
const MODE = process.env.QUOTE_MODE || 'mock';
const ONEINCH_API_KEY = process.env.ONEINCH_API_KEY || '';
const MOCK_PRICE_X1E6 = Number(process.env.MOCK_PRICE_X1E6 || 3200000000);

function json(res, status, body) {
  res.status(status).type('application/json').send(JSON.stringify(body));
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
      source: 'mock-1inch-compatible-relayer'
    });
  }

  if (!ONEINCH_API_KEY) {
    return json(res, 503, { error: 'ONEINCH_API_KEY is required in live mode' });
  }

  // This endpoint is deliberately a thin proxy. It makes no verdict decision.
  // Integrate the current 1inch quote endpoint here and normalize only the
  // resulting quote into price_x1e6 before returning it to the contract.
  return json(res, 501, {
    error: 'Live adapter not configured',
    detail: 'Set ONEINCH_API_KEY and implement the network-specific 1inch adapter.'
  });
});

app.listen(PORT, () => console.log(`Agent Judge relayer listening on :${PORT} (${MODE})`));
