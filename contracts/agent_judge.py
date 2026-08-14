# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


class AgentJudge(gl.Contract):
    """Minimal trust-minimized judge for agent answers against live market data.

    The contract stores task/answer/verdict state deterministically. Only the
    external quote fetch is non-deterministic and is resolved with strict_eq.
    """

    task_data: TreeMap[str, str]
    task_status: TreeMap[str, u8]
    task_agent: TreeMap[str, str]
    task_answer: TreeMap[str, str]
    task_verdict: TreeMap[str, str]
    reputation: TreeMap[str, u32]
    dispute_count: TreeMap[str, u32]
    task_nonce: u64

    def __init__(self):
        self.task_nonce = u64(0)

    @gl.public.write
    def create_task(self, prompt: str, reference_value: str, tolerance_bps: u32) -> str:
        if tolerance_bps == 0 or tolerance_bps > 1000:
            raise gl.vm.UserError("tolerance_bps must be between 1 and 1000")
        task_id = "task-" + str(self.task_nonce)
        self.task_nonce += u64(1)
        payload = json.dumps({
            "prompt": prompt,
            "reference_value": reference_value,
            "tolerance_bps": int(tolerance_bps),
        }, sort_keys=True)
        self.task_data[task_id] = payload
        self.task_status[task_id] = u8(1)  # OPEN
        self.task_agent[task_id] = ""
        self.task_answer[task_id] = ""
        self.task_verdict[task_id] = "PENDING"
        return task_id

    @gl.public.write
    def submit_answer(self, task_id: str, answer_value: str, agent_label: str) -> None:
        if self.task_status.get(task_id, u8(0)) != u8(1):
            raise gl.vm.UserError("task is not open")
        if answer_value == "":
            raise gl.vm.UserError("answer_value is required")
        self.task_agent[task_id] = agent_label
        self.task_answer[task_id] = answer_value
        self.task_status[task_id] = u8(2)  # ANSWERED

    def _quote_snapshot(self, pair: str, reference_value: str) -> str:
        """External data must only run in a nondeterministic block.

        The relayer endpoint is intentionally configurable at deployment time
        through this contract constant. The endpoint returns a normalized
        integer representation, keeping strict_eq deterministic after parsing.
        """
        url = "https://agent-judge-relayer.example/quote?pair=" + pair + "&reference=" + reference_value
        response = gl.nondet.web.request(url, method="GET")
        body = response.body.decode("utf-8")
        data = json.loads(body)
        # Only stable, normalized fields participate in consensus.
        return json.dumps({
            "pair": str(data["pair"]),
            "price_x1e6": int(data["price_x1e6"]),
            "source": str(data["source"]),
        }, sort_keys=True)

    @gl.public.write
    def evaluate(self, task_id: str, pair: str) -> str:
        if self.task_status.get(task_id, u8(0)) != u8(2):
            raise gl.vm.UserError("task must have a submitted answer")

        task = json.loads(self.task_data[task_id])
        answer = float(self.task_answer[task_id])
        reference = float(task["reference_value"])
        tolerance_bps = int(task["tolerance_bps"])

        # Snapshot is fetched only through the Equivalence Principle.
        snapshot_json = gl.eq_principle.strict_eq(
            lambda: self._quote_snapshot(pair, task["reference_value"])
        )
        snapshot = json.loads(snapshot_json)
        live_price = float(snapshot["price_x1e6"]) / 1_000_000.0

        # Compare the submitted answer with the authoritative live value.
        diff_bps = abs(answer - live_price) / live_price * 10_000.0
        # reference_value is retained as the task's declared benchmark for auditability.
        reference_check_bps = abs(live_price - reference) / live_price * 10_000.0
        accepted = diff_bps <= tolerance_bps
        verdict = {
            "accepted": accepted,
            "answer": answer,
            "live_price": live_price,
            "reference_value": reference,
            "difference_bps": diff_bps,
            "reference_difference_bps": reference_check_bps,
            "tolerance_bps": tolerance_bps,
            "source": snapshot["source"],
        }
        self.task_verdict[task_id] = json.dumps(verdict, sort_keys=True)
        self.task_status[task_id] = u8(3) if accepted else u8(4)

        agent = self.task_agent[task_id]
        if agent != "" and accepted:
            self.reputation[agent] = self.reputation.get(agent, u32(0)) + u32(1)
        return self.task_verdict[task_id]

    @gl.public.write
    def dispute(self, task_id: str, pair: str) -> str:
        status = self.task_status.get(task_id, u8(0))
        if status != u8(3) and status != u8(4):
            raise gl.vm.UserError("only completed tasks can be disputed")
        self.dispute_count[task_id] = self.dispute_count.get(task_id, u32(0)) + u32(1)
        # Re-evaluation uses a newly fetched live snapshot. This is intentionally
        # simple for MVP and avoids pretending an old external snapshot is final.
        return self.evaluate(task_id, pair)

    @gl.public.view
    def get_task(self, task_id: str) -> str:
        return json.dumps({
            "task_id": task_id,
            "data": self.task_data.get(task_id, ""),
            "status": int(self.task_status.get(task_id, u8(0))),
            "agent": self.task_agent.get(task_id, ""),
            "answer": self.task_answer.get(task_id, ""),
            "verdict": self.task_verdict.get(task_id, "PENDING"),
            "disputes": int(self.dispute_count.get(task_id, u32(0))),
        }, sort_keys=True)

    @gl.public.view
    def get_reputation(self, agent_label: str) -> u32:
        return self.reputation.get(agent_label, u32(0))
