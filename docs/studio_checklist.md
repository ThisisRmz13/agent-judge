# Studio submission checklist

- [ ] Load `contracts/agent_judge.py` into GenLayer Studio.
- [ ] Set the constructor argument `relayer_url` to the deployed Cloudflare Worker URL (an empty or `.example` URL is rejected).
- [ ] Deploy the contract.
- [ ] Copy the deployed contract address into `frontend`.
- [ ] Run the frontend with `npm install && npm run dev`.
- [ ] Connect a wallet to Studionet.
- [ ] Call `create_task("Return the current ETH/USDC price within tolerance.", "3200", 50, "ETHUSDC")`.
- [ ] Copy the returned task id from the transaction/debug trace.
- [ ] Call `submit_answer(task_id, "3200", "demo-agent")`.
- [ ] Verify `get_task(task_id)` shows status `2` before evaluation.
- [ ] Configure a reachable relayer endpoint in the contract before testing `evaluate`.
- [ ] Run `evaluate(task_id)`.
- [ ] Verify the verdict is persisted in `get_task`.
- [ ] Verify `get_reputation("demo-agent")` increments after an accepted verdict.
- [ ] Test `dispute(task_id)` on a completed task.
- [ ] Capture screenshots of deployment and at least one successful evaluation.
- [ ] Do not upload `.env`, provider keys, `node_modules`, or local credentials.
