# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
from datetime import datetime, timezone
from urllib.parse import quote


class AgentJudge(gl.Contract):
    """Trust-minimized judge for agent answers against relayed market data."""

    MAX_QUOTE_AGE_MS = 60_000

    task_data: TreeMap[str, str]
    task_status: TreeMap[str, u8]
    task_creator: TreeMap[str, Address]
    task_agent: TreeMap[str, str]
    task_answer: TreeMap[str, str]
    task_verdict: TreeMap[str, str]
    reputation: TreeMap[str, u32]
    reputation_credited: TreeMap[str, bool]
    dispute_count: TreeMap[str, u32]
    task_nonce: u64
    relayer_url: str

    def __init__(self, relayer_url: str):
        if relayer_url == "" or ".example" in relayer_url:
            raise gl.vm.UserError("a real relayer_url is required")
        self.task_nonce = u64(0)
        self.relayer_url = relayer_url.rstrip("/")

    @gl.public.write
    def create_task(self, prompt: str, reference_value: str, tolerance_bps: u32, pair: str) -> str:
        if tolerance_bps == 0 or tolerance_bps > 1000:
            raise gl.vm.UserError("tolerance_bps must be between 1 and 1000")
        normalized_pair = self._normalize_pair(pair)
        if normalized_pair == "":
            raise gl.vm.UserError("pair is required")
        task_id = "task-" + str(self.task_nonce)
        self.task_nonce += u64(1)
        self.task_data[task_id] = json.dumps({"prompt": prompt, "reference_value": reference_value, "tolerance_bps": int(tolerance_bps), "pair": normalized_pair}, sort_keys=True)
        self.task_status[task_id] = u8(1)
        self.task_creator[task_id] = gl.message.sender_address
        self.task_agent[task_id] = ""
        self.task_answer[task_id] = ""
        self.task_verdict[task_id] = "PENDING"
        self.reputation_credited[task_id] = False
        self.dispute_count[task_id] = u32(0)
        return task_id

    @gl.public.write
    def submit_answer(self, task_id: str, answer_value: str, agent_label: str) -> None:
        if self.task_status.get(task_id, u8(0)) != u8(1):
            raise gl.vm.UserError("task is not open")
        if answer_value == "" or agent_label == "":
            raise gl.vm.UserError("answer_value and agent_label are required")
        self.task_agent[task_id] = agent_label
        self.task_answer[task_id] = answer_value
        self.task_status[task_id] = u8(2)

    def _normalize_pair(self, pair: str) -> str:
        return str(pair).upper().replace("/", "")

    def _quote_snapshot(self, pair: str, reference_value: str) -> str:
        requested_pair = self._normalize_pair(pair)
        if requested_pair == "":
            raise gl.vm.UserError("pair is required")
        url = self.relayer_url + "/quote?pair=" + quote(pair, safe="") + "&reference=" + quote(reference_value, safe="")
        try:
            response = gl.nondet.web.request(url, method="GET")
        except Exception:
            raise gl.vm.UserError("live quote request failed")
        try:
            body = response.body.decode("utf-8")
            data = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise gl.vm.UserError("relayer returned malformed JSON")
        if not isinstance(data, dict):
            raise gl.vm.UserError("relayer response is malformed")
        required_fields = {"pair", "price_x1e6", "source", "timestamp_ms", "age_ms", "fresh", "reference"}
        if not required_fields.issubset(data):
            raise gl.vm.UserError("relayer response is missing required fields")
        returned_pair = self._normalize_pair(str(data["pair"]))
        if returned_pair != requested_pair:
            raise gl.vm.UserError("relayer returned a different trading pair")
        if str(data["source"]) != "binance-spot":
            raise gl.vm.UserError("quote source is not the approved live source")
        if str(data["reference"]) != str(reference_value):
            raise gl.vm.UserError("relayer returned a different reference")
        if not bool(data["fresh"]):
            raise gl.vm.UserError("relayer returned a stale quote")
        try:
            age_ms = int(data["age_ms"])
            timestamp_ms = int(data["timestamp_ms"])
            price_x1e6 = int(data["price_x1e6"])
        except (TypeError, ValueError):
            raise gl.vm.UserError("relayer response contains invalid numeric fields")
        if age_ms < 0 or age_ms > self.MAX_QUOTE_AGE_MS:
            raise gl.vm.UserError("relayer returned a stale quote")
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        if timestamp_ms <= 0 or timestamp_ms > now_ms:
            raise gl.vm.UserError("relayer returned an invalid quote timestamp")
        if price_x1e6 <= 0:
            raise gl.vm.UserError("relayer returned an invalid price")
        return json.dumps({"pair": str(data["pair"]), "price_x1e6": price_x1e6, "source": str(data["source"]), "timestamp_ms": timestamp_ms, "age_ms": age_ms, "fresh": True}, sort_keys=True)

    def _evaluate(self, task_id: str) -> str:
        task = json.loads(self.task_data[task_id])
        pair = str(task["pair"])
        answer = float(self.task_answer[task_id])
        reference = float(task["reference_value"])
        tolerance_bps = int(task["tolerance_bps"])
        snapshot_json = gl.eq_principle.prompt_comparative(
            lambda: self._quote_snapshot(pair, task["reference_value"]),
            principle="""
            Both results are a JSON object describing one market quote.
            The pair, source, and reference must match. Price values may differ by up to 50 bps because validators fetch independently.
            Timestamp and age may differ because validators fetch at different moments, provided freshness was enforced.
            Reject if pair, source, or reference differ, fresh is false, age exceeds 60 seconds, timestamp is in the future, or price difference exceeds 50 bps.
            """,
        )
        snapshot = json.loads(snapshot_json)
        live_price = float(snapshot["price_x1e6"]) / 1_000_000.0
        if live_price <= 0:
            raise gl.vm.UserError("relayer returned an invalid price")
        diff_bps = abs(answer - live_price) / live_price * 10_000.0
        reference_check_bps = abs(live_price - reference) / live_price * 10_000.0
        accepted = diff_bps <= tolerance_bps
        old_verdict = self.task_verdict.get(task_id, "PENDING")
        old_accepted = False if old_verdict == "PENDING" else bool(json.loads(old_verdict).get("accepted", False))
        verdict = {"accepted": accepted, "answer": answer, "live_price": live_price, "reference_value": reference, "difference_bps": diff_bps, "reference_difference_bps": reference_check_bps, "tolerance_bps": tolerance_bps, "pair": pair, "source": snapshot["source"], "quote_timestamp_ms": snapshot["timestamp_ms"], "quote_age_ms": snapshot["age_ms"], "disputed": int(self.dispute_count.get(task_id, u32(0))) > 0}
        self.task_verdict[task_id] = json.dumps(verdict, sort_keys=True)
        self.task_status[task_id] = u8(3) if accepted else u8(4)
        agent = self.task_agent[task_id]
        if agent != "" and accepted and not old_accepted:
            self.reputation[agent] = self.reputation.get(agent, u32(0)) + u32(1)
            self.reputation_credited[task_id] = True
        elif agent != "" and old_accepted and not accepted and self.reputation_credited.get(task_id, False):
            current = self.reputation.get(agent, u32(0))
            if current > u32(0):
                self.reputation[agent] = current - u32(1)
            self.reputation_credited[task_id] = False
        return self.task_verdict[task_id]

    @gl.public.write
    def evaluate(self, task_id: str) -> str:
        if self.task_status.get(task_id, u8(0)) != u8(2):
            raise gl.vm.UserError("task must have a submitted answer")
        return self._evaluate(task_id)

    @gl.public.write
    def dispute(self, task_id: str) -> str:
        if self.task_creator.get(task_id, Address("0x0000000000000000000000000000000000000000")) != gl.message.sender_address:
            raise gl.vm.UserError("only the task creator can dispute")
        status = self.task_status.get(task_id, u8(0))
        if status != u8(3) and status != u8(4):
            raise gl.vm.UserError("only completed tasks can be disputed")
        if self.dispute_count.get(task_id, u32(0)) != u32(0):
            raise gl.vm.UserError("task has already been disputed")
        self.dispute_count[task_id] = u32(1)
        return self._evaluate(task_id)

    @gl.public.view
    def get_task(self, task_id: str) -> str:
        verdict = self.task_verdict.get(task_id, "PENDING")
        if verdict != "PENDING":
            verdict = json.loads(verdict)
        return json.dumps({"task_id": task_id, "data": self.task_data.get(task_id, ""), "status": int(self.task_status.get(task_id, u8(0))), "creator": str(self.task_creator.get(task_id, Address("0x0000000000000000000000000000000000000000"))), "agent": self.task_agent.get(task_id, ""), "answer": self.task_answer.get(task_id, ""), "verdict": verdict, "disputes": int(self.dispute_count.get(task_id, u32(0)) )}, sort_keys=True)

    @gl.public.view
    def get_reputation(self, agent_label: str) -> u32:
        return self.reputation.get(agent_label, u32(0))
