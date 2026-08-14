import { createClient } from 'genlayer-js';
import { studionet } from 'genlayer-js/chains';

const state = { client: null, account: null, contract: '' };

const app = document.querySelector('#app');
app.innerHTML = `
  <div class="wrap">
    <header><h1>Agent Judge</h1><p>On-chain task evaluation with GenLayer consensus.</p></header>
    <section class="card">
      <h2>Connection</h2>
      <input id="contract" placeholder="Deployed contract address" />
      <button id="connect">Connect wallet</button>
      <div id="account" class="muted">Disconnected</div>
    </section>
    <section class="grid">
      <div class="card">
        <h2>Create task</h2>
        <input id="prompt" value="Return the current ETH/USDC price within tolerance." />
        <input id="reference" value="3200" />
        <input id="tolerance" value="50" type="number" />
        <button id="create">Create task</button>
      </div>
      <div class="card">
        <h2>Submit answer</h2>
        <input id="task" placeholder="task id" />
        <input id="agent" value="demo-agent" />
        <input id="answer" value="3200" />
        <button id="submit">Submit</button>
      </div>
    </section>
    <section class="card">
      <h2>Evaluate and inspect</h2>
      <input id="pair" value="ETH/USDC" />
      <button id="evaluate">Evaluate</button>
      <button id="read">Read task</button>
      <button id="reputation">Read reputation</button>
      <pre id="output">Ready.</pre>
    </section>
  </div>
`;

const style = document.createElement('style');
style.textContent = `
  :root{font-family:Inter,system-ui,sans-serif;background:#0a0c0f;color:#eef2f7}
  body{margin:0;background:#0a0c0f}.wrap{max-width:980px;margin:0 auto;padding:34px 18px}
  header{margin-bottom:18px}.muted{color:#9aa5b1;margin-top:8px;font-size:14px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:750px){.grid{grid-template-columns:1fr}}
  .card{background:#12161b;border:1px solid #29313a;border-radius:14px;padding:18px;margin:16px 0}
  h1{margin-bottom:4px}h2{font-size:16px}
  input,button{width:100%;box-sizing:border-box;padding:11px 12px;margin:6px 0;border-radius:8px;border:1px solid #38414c;background:#0d1014;color:#eef2f7}
  button{cursor:pointer;background:#1c242d}.ok{color:#9dd6a9}.err{color:#f0a7a7}
  pre{background:#0c0f13;border-radius:8px;padding:14px;min-height:90px;white-space:pre-wrap;overflow:auto}
`;
document.head.appendChild(style);

const $ = (id) => document.getElementById(id);
const out = (value, error = false) => {
  $('output').textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  $('output').className = error ? 'err' : 'ok';
};

async function connect() {
  if (!window.ethereum) throw new Error('MetaMask or another EIP-1193 wallet is required.');
  const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
  state.account = accounts[0];
  state.contract = $('contract').value.trim();
  if (!state.contract) throw new Error('Enter the deployed contract address first.');
  state.client = createClient({
    chain: studionet,
    account: state.account,
    provider: window.ethereum,
  });
  await state.client.connect('studionet');
  $('account').textContent = `Connected: ${state.account}`;
  out('Connected to Studionet.');
}

function requireClient() {
  if (!state.client) throw new Error('Connect the wallet first.');
  return state.client;
}

async function write(functionName, args) {
  const client = requireClient();
  state.contract = $('contract').value.trim();
  if (!state.contract) throw new Error('Contract address is required.');
  const hash = await client.writeContract({
    address: state.contract,
    functionName,
    args,
    value: BigInt(0),
  });
  return client.waitForTransactionReceipt({ hash, status: 'ACCEPTED' });
}

$('connect').onclick = async () => { try { await connect(); } catch (e) { out(e.message, true); } };
$('create').onclick = async () => {
  try {
    const receipt = await write('create_task', [
      $('prompt').value,
      $('reference').value,
      Number($('tolerance').value),
    ]);
    out(receipt);
  } catch (e) { out(e.message, true); }
};
$('submit').onclick = async () => {
  try {
    const receipt = await write('submit_answer', [$('task').value.trim(), $('answer').value, $('agent').value]);
    out(receipt);
  } catch (e) { out(e.message, true); }
};
$('evaluate').onclick = async () => {
  try {
    const receipt = await write('evaluate', [$('task').value.trim(), $('pair').value.trim()]);
    out(receipt);
  } catch (e) { out(e.message, true); }
};
$('read').onclick = async () => {
  try {
    const client = requireClient();
    const result = await client.readContract({
      address: $('contract').value.trim(), functionName: 'get_task', args: [$('task').value.trim()]
    });
    out(result);
  } catch (e) { out(e.message, true); }
};
$('reputation').onclick = async () => {
  try {
    const client = requireClient();
    const result = await client.readContract({
      address: $('contract').value.trim(), functionName: 'get_reputation', args: [$('agent').value]
    });
    out(result);
  } catch (e) { out(e.message, true); }
};
