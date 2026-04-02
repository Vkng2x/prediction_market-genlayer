# v4.1.0
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json
import typing
from datetime import datetime, timezone

VERSION = "4.1.0"

# ── Market constants ─────────────────────────────────────────────────────────
PLATFORM_FEE_PERCENT          = 2
APPEAL_FEE                    = 50
MIN_BET                       = 10
MAX_BET                       = 10000
MAX_BETS_PER_MARKET           = 100
MAX_BETS_PER_ADDRESS_PER_MARKET = 3
MAX_MARKETS_PER_ADDRESS       = 20
MAX_APPEALS_PER_ADDRESS       = 3

# ── Resolution constants ─────────────────────────────────────────────────────
AI_MODEL_COUNT                = 3
AI_CONSENSUS_THRESHOLD        = 2   # how many models must agree
RESOLVER_STAKE_REQUIRED       = 50
SLASH_PERCENT_ON_OVERRIDE     = 50
MIN_EVIDENCE_LENGTH           = 300  # chars required from resolution_url


# ── Deadline helper (module-level so it can be patched in tests) ─────────────

def _parse_iso_deadline(deadline_str: str) -> datetime:
    """
    Parse an ISO-8601 deadline string into a UTC-aware datetime.
    Accepts:  "2026-12-31"
              "2026-12-31T23:59:59"
              "2026-12-31T23:59:59Z"
              "2026-12-31T23:59:59+00:00"
    Raises a clear Exception on any invalid input.
    """
    if not deadline_str or not deadline_str.strip():
        raise Exception("deadline_str is empty — cannot enforce deadline gate")

    s = deadline_str.strip()
    if "T" not in s:
        s += "T00:00:00Z"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise Exception(
            f"deadline_str '{deadline_str}' is not valid ISO-8601. "
            "Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ"
        )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _now_utc() -> datetime:
    """Current UTC time — wrapped so tests can patch it."""
    return datetime.now(timezone.utc)


# ── Contract ─────────────────────────────────────────────────────────────────

class PredictionMarket(gl.Contract):
    markets:             TreeMap[str, str]
    bets:                TreeMap[str, str]
    appeal_requests:     TreeMap[str, str]
    balances:            TreeMap[str, str]
    stakes:              TreeMap[str, str]
    paused:              bool
    owner:               str
    auto_resolver:       str
    address_market_count: TreeMap[str, str]
    address_appeal_count: TreeMap[str, str]
    address_bet_counts:  TreeMap[str, str]
    tx_counter:          str

    def __init__(self):
        self.paused       = False
        self.owner        = "unknown"
        self.auto_resolver = ""
        self.tx_counter   = "0"

    # ── Tiny shared utilities ─────────────────────────────────────────────

    def _next_tx(self) -> int:
        n = int(self.tx_counter) + 1
        self.tx_counter = str(n)
        return n

    def _check_not_paused(self):
        if self.paused:
            raise Exception("Contract is paused")

    def _greybox(self, text: str, field: str) -> None:
        """Block obvious prompt-injection attempts."""
        banned = [
            "ignore previous", "forget instructions",
            "system prompt", "ignore above",
            "disregard", "override instructions",
        ]
        for phrase in banned:
            if phrase in text.lower():
                raise Exception(f"Prompt injection detected in {field}")

    def _validate_https_url(self, url: str) -> None:
        if url and not url.startswith("https://"):
            raise Exception("resolution_url must start with https://")

    def _sender(self) -> str:
        try:
            return str(gl.message.sender_address)
        except Exception:
            return "unknown"

    # ── Balance helpers ───────────────────────────────────────────────────

    def _add_to_platform(self, amount: int) -> None:
        cur = int(self.balances["platform"]) if "platform" in self.balances else 0
        self.balances["platform"] = str(cur + amount)

    def _add_to_balance(self, user: str, amount: int) -> None:
        cur = int(self.balances[user]) if user in self.balances else 0
        self.balances[user] = str(cur + amount)

    # ── Counter helpers ───────────────────────────────────────────────────

    def _incr(self, tree: TreeMap, key: str) -> int:
        cur = int(tree[key]) if key in tree else 0
        tree[key] = str(cur + 1)
        return cur + 1

    # ── Re-entrancy lock ──────────────────────────────────────────────────

    def _acquire_claim_lock(self, bet_id: str) -> None:
        bet = json.loads(self.bets[bet_id])
        if bet.get("_lock"):
            raise Exception("Re-entrancy: claim in progress")
        bet["_lock"] = True
        self.bets[bet_id] = json.dumps(bet)

    def _release_claim_lock(self, bet_id: str) -> None:
        bet = json.loads(self.bets[bet_id])
        bet["_lock"] = False
        self.bets[bet_id] = json.dumps(bet)

    # ── URL fetcher (single implementation, used by resolve + appeal) ─────

    def _fetch_url(self, url: str) -> str:
        """
        Fetch a URL and return up to 5000 chars of body text.
        Returns "" on any network or decode error — callers must gate on length.
        """
        if not url:
            return ""

        def fetch() -> typing.Any:
            try:
                response = gl.nondet.web.get(url)
                return response.body.decode("utf-8")[:5000]
            except Exception:
                return ""

        def validate(res) -> bool:
            return isinstance(res, gl.vm.Return)

        result = gl.vm.run_nondet_unsafe(fetch, validate)
        return result if isinstance(result, str) else ""

    # ════════════════════════════════════════════════════════════════════════
    # TRUTH GATES
    # ════════════════════════════════════════════════════════════════════════

    def _gate_deadline(self, deadline_str: str) -> None:
        """
        Gate 1 — real-world UTC clock must be past the market deadline.
        Raises with exact time remaining so callers know when to retry.
        """
        deadline_dt = _parse_iso_deadline(deadline_str)
        now = _now_utc()
        if now < deadline_dt:
            delta = int((deadline_dt - now).total_seconds())
            h, m = delta // 3600, (delta % 3600) // 60
            raise Exception(
                f"Truth Gate 1 FAILED — deadline not reached. "
                f"Deadline: {deadline_dt.isoformat()}. "
                f"Time remaining: {h}h {m}m UTC."
            )

    def _gate_evidence(self, web_data: str, url: str) -> None:
        """
        Gate 2 — resolution_url must return real content (>= MIN_EVIDENCE_LENGTH chars).
        Blocks empty fetches, 404 stubs, and login walls.
        """
        if len(web_data.strip()) < MIN_EVIDENCE_LENGTH:
            raise Exception(
                f"Truth Gate 2 FAILED — insufficient evidence. "
                f"Got {len(web_data.strip())} chars from {url}, "
                f"need at least {MIN_EVIDENCE_LENGTH}. "
                f"Resolution blocked until verifiable data is available."
            )

    def _gate_relevance(self, question: str, web_data: str) -> str:
        """
        Gate 3 — AI must confirm the page directly answers the question
        before it is allowed to vote on the outcome.
        Returns the evidence reason string (stored on the market for audit).
        """
        excerpt = web_data[:2000]

        def check() -> typing.Any:
            task = f"""You are a strict evidence auditor for a prediction market.

Decide whether the web page below contains factual, verifiable information
that directly answers whether this question is YES or NO.

Question: {question}

Page content (first 2000 chars):
{excerpt}

Rules:
- Return false for login walls, 404 pages, generic homepages, or unrelated articles.
- Return false if the page discusses the topic generally but lacks specific outcome facts.
- Return true ONLY if the page contains direct evidence of the actual outcome.

Return ONLY valid JSON:
{{"answers_question": true,  "reason": "one factual sentence citing what evidence was found"}}
{{"answers_question": false, "reason": "one sentence explaining what is missing"}}"""
            result = gl.nondet.exec_prompt(task, response_format="json")
            if not isinstance(result, dict):
                raise Exception("Relevance check: bad response type")
            if result.get("answers_question") not in [True, False]:
                raise Exception("Relevance check: missing boolean")
            if not isinstance(result.get("reason"), str) or len(result["reason"]) < 10:
                raise Exception("Relevance check: reason too short")
            return result

        def validate(res) -> bool:
            if not isinstance(res, gl.vm.Return):
                return False
            d = res.calldata
            return (
                isinstance(d, dict)
                and d.get("answers_question") in [True, False]
                and isinstance(d.get("reason"), str)
                and len(d.get("reason", "")) >= 10
            )

        result = gl.vm.run_nondet_unsafe(check, validate)

        if not result["answers_question"]:
            raise Exception(
                f"Truth Gate 3 FAILED — page does not answer the question. "
                f"Reason: {result['reason']}"
            )
        return result["reason"]

    # ── Multi-model AI resolver (runs ONLY after all three gates pass) ─────

    def _multi_ai_resolve(self, question: str, web_data: str, context: str) -> dict:
        """
        Runs AI_MODEL_COUNT independent models.
        Requires AI_CONSENSUS_THRESHOLD to agree on the same outcome.
        Raises if no consensus is reached.
        """
        results = []

        for i in range(AI_MODEL_COUNT):
            def get_one(idx=i) -> typing.Any:
                task = f"""[Model {idx+1}/{AI_MODEL_COUNT}] Prediction market resolver.
{context}
Question: {question}
Verified web evidence: {web_data}
Return ONLY valid JSON:
{{"outcome": "YES", "reasoning": "factual sentence min 20 chars citing the evidence", "confidence": "high|medium|low"}}
{{"outcome": "NO",  "reasoning": "factual sentence min 20 chars citing the evidence", "confidence": "high|medium|low"}}"""
                result = gl.nondet.exec_prompt(task, response_format="json")
                if not isinstance(result, dict):
                    raise Exception(f"Model {idx+1}: bad response")
                outcome = str(result.get("outcome", "")).upper().strip()
                if outcome not in ["YES", "NO"]:
                    raise Exception(f"Model {idx+1}: invalid outcome '{outcome}'")
                reasoning = str(result.get("reasoning", ""))
                if len(reasoning) < 15:
                    raise Exception(f"Model {idx+1}: reasoning too short")
                confidence = result.get("confidence", "medium")
                if confidence not in ["high", "medium", "low"]:
                    confidence = "medium"
                return {"outcome": outcome, "reasoning": reasoning, "confidence": confidence}

            def validate_one(res) -> bool:
                if not isinstance(res, gl.vm.Return):
                    return False
                d = res.calldata
                return (
                    isinstance(d, dict)
                    and d.get("outcome") in ["YES", "NO"]
                    and isinstance(d.get("reasoning"), str)
                    and len(d.get("reasoning", "")) >= 15
                    and d.get("confidence") in ["high", "medium", "low"]
                )

            results.append(gl.vm.run_nondet_unsafe(get_one, validate_one))

        yes_votes = sum(1 for r in results if r["outcome"] == "YES")
        no_votes  = AI_MODEL_COUNT - yes_votes

        if yes_votes >= AI_CONSENSUS_THRESHOLD:
            winning = "YES"
        elif no_votes >= AI_CONSENSUS_THRESHOLD:
            winning = "NO"
        else:
            raise Exception(f"No consensus: {yes_votes} YES vs {no_votes} NO")

        winner = next(r for r in results if r["outcome"] == winning)
        return {
            "outcome":    winning,
            "reasoning":  winner["reasoning"],
            "confidence": winner["confidence"],
            "votes":      {"yes": yes_votes, "no": no_votes},
        }

    # ════════════════════════════════════════════════════════════════════════
    # PUBLIC WRITE METHODS
    # ════════════════════════════════════════════════════════════════════════

    @gl.public.write
    def emergency_pause(self) -> None:
        self.paused = True

    @gl.public.write
    def emergency_unpause(self) -> None:
        self.paused = False

    @gl.public.write
    def set_auto_resolver(self, addr: str) -> None:
        if not addr or len(addr) < 5:
            raise Exception("Invalid resolver address")
        self.auto_resolver = addr

    @gl.public.write
    def deposit_resolver_stake(self, resolver_id: str, amount: int) -> None:
        self._check_not_paused()
        if amount < RESOLVER_STAKE_REQUIRED:
            raise Exception(f"Min stake is {RESOLVER_STAKE_REQUIRED}")
        cur = int(self.stakes[resolver_id]) if resolver_id in self.stakes else 0
        self.stakes[resolver_id] = str(cur + amount)

    @gl.public.write
    def withdraw_resolver_stake(self, resolver_id: str) -> str:
        if resolver_id not in self.stakes:
            raise Exception("No stake found")
        amount = int(self.stakes[resolver_id])
        if amount <= 0:
            raise Exception("Zero stake")
        self.stakes[resolver_id] = "0"
        return str(amount)

    @gl.public.write
    def create_market(
        self,
        market_id:      str,
        question:       str,
        deadline_str:   str,
        resolution_url: str,
    ) -> None:
        self._check_not_paused()

        if market_id in self.markets:
            raise Exception("Market already exists")
        if not (10 <= len(question) <= 500):
            raise Exception("Question must be 10–500 characters")
        if len(market_id) > 50:
            raise Exception("Market ID too long (max 50 chars)")
        if not resolution_url:
            raise Exception("resolution_url is required")
        if len(resolution_url) > 300:
            raise Exception("resolution_url too long (max 300 chars)")

        self._greybox(question, "question")
        self._validate_https_url(resolution_url)

        # Validate and normalise deadline at creation time
        deadline_dt = _parse_iso_deadline(deadline_str)
        if deadline_dt <= _now_utc():
            raise Exception(
                f"deadline_str '{deadline_str}' is in the past. "
                "Example valid values: '2026-12-31' or '2027-06-01T00:00:00Z'"
            )

        creator = self._sender()
        if self._incr(self.address_market_count, creator) > MAX_MARKETS_PER_ADDRESS:
            raise Exception(f"Max {MAX_MARKETS_PER_ADDRESS} markets per address")

        # AI resolvability check (informational — does not block creation)
        def check_resolvable() -> typing.Any:
            task = f"""Prediction market validator.
The market deadline is {deadline_str}. At or after that date, can this question
be definitively answered YES or NO from public verifiable facts?
Question: {question}
Return ONLY valid JSON:
{{"valid": true,  "reason": "one sentence"}}
{{"valid": false, "reason": "one sentence"}}"""
            result = gl.nondet.exec_prompt(task, response_format="json")
            return result if isinstance(result, dict) else {"valid": True, "reason": "validator unavailable"}

        ai_check = gl.vm.run_nondet_unsafe(
            check_resolvable,
            lambda res: isinstance(res, gl.vm.Return) and isinstance(res.calldata, dict),
        )

        self.markets[market_id] = json.dumps({
            "version":              VERSION,
            "question":             question,
            "deadline_str":         deadline_str,
            "deadline_iso":         deadline_dt.isoformat(),
            "created_at_tx":        self._next_tx(),
            "resolution_url":       resolution_url,
            "status":               "open",
            "yes_pool":             0,
            "no_pool":              0,
            "outcome":              "PENDING",
            "reasoning":            "",
            "confidence":           "unknown",
            "data_source":          "unknown",
            "votes":                {},
            "appeal_count":         0,
            "last_appeal_tx":       0,
            "total_fees_collected": 0,
            "creator":              creator,
            "resolver":             "",
            "bet_count":            0,
            "is_cancelled":         False,
            "is_final":             False,
            "evidence_reason":      "",
            "ai_validation_passed": ai_check.get("valid", True),
            "ai_validation_reason": ai_check.get("reason", ""),
        })

    @gl.public.write
    def place_bet(self, market_id: str, bet_id: str, side: str, amount: int) -> None:
        self._check_not_paused()

        if market_id not in self.markets:
            raise Exception("Market not found")
        if bet_id in self.bets:
            raise Exception("Bet ID already exists — use a unique bet_id")
        if not (MIN_BET <= amount <= MAX_BET):
            raise Exception(f"Bet amount must be {MIN_BET}–{MAX_BET}")

        market = json.loads(self.markets[market_id])

        if market.get("is_cancelled"):
            raise Exception("Market is cancelled")
        if market["status"] != "open":
            raise Exception("Market is not open")
        if market["bet_count"] >= MAX_BETS_PER_MARKET:
            raise Exception("Bet limit reached for this market")
        if side.upper() not in ["YES", "NO"]:
            raise Exception("Side must be YES or NO")

        bettor = self._sender()
        if self._incr(self.address_bet_counts, f"{market_id}:{bettor}") > MAX_BETS_PER_ADDRESS_PER_MARKET:
            raise Exception(f"Max {MAX_BETS_PER_ADDRESS_PER_MARKET} bets per address per market")

        fee        = max(1, (amount * PLATFORM_FEE_PERCENT) // 100)
        net_amount = amount - fee
        self._add_to_platform(fee)
        market["total_fees_collected"] += fee
        market["bet_count"]            += 1

        side = side.upper()
        self.bets[bet_id] = json.dumps({
            "market_id":    market_id,
            "side":         side,
            "amount":       net_amount,
            "gross_amount": amount,
            "fee_paid":     fee,
            "bettor":       bettor,
            "claimed":      False,
            "refunded":     False,
            "placed_at_tx": self._next_tx(),
            "bet_number":   market["bet_count"],
            "_lock":        False,
        })

        if side == "YES":
            market["yes_pool"] += net_amount
        else:
            market["no_pool"] += net_amount

        self.markets[market_id] = json.dumps(market)

    @gl.public.write
    def resolve_market(self, market_id: str, resolver_id: str) -> None:
        """
        Resolves a market. All three Truth Gates must pass:
          Gate 1 — deadline has passed (UTC clock)
          Gate 2 — resolution_url returns >= MIN_EVIDENCE_LENGTH chars
          Gate 3 — AI confirms the page directly answers the question
        Only then do the AI models vote. is_final is set only on success.
        Any gate failure raises without changing market state.
        """
        self._check_not_paused()

        if market_id not in self.markets:
            raise Exception("Market not found")

        market = json.loads(self.markets[market_id])

        if market.get("is_final"):
            raise Exception("Market is permanently finalized")
        if market["status"] == "resolved":
            raise Exception("Market is already resolved")
        if market.get("is_cancelled"):
            raise Exception("Market is cancelled")
        if market["yes_pool"] == 0 or market["no_pool"] == 0:
            raise Exception("Need bets on both sides before resolving")

        stake = int(self.stakes[resolver_id]) if resolver_id in self.stakes else 0
        if stake < RESOLVER_STAKE_REQUIRED:
            raise Exception(
                f"Resolver needs a stake of {RESOLVER_STAKE_REQUIRED}. "
                "Call deposit_resolver_stake() first."
            )

        question       = market["question"]
        resolution_url = market.get("resolution_url", "")
        self._greybox(question, "question")

        # Gate 1 — deadline
        self._gate_deadline(market.get("deadline_iso") or market.get("deadline_str", ""))

        # Gate 2 — evidence exists
        web_data = self._fetch_url(resolution_url)
        self._gate_evidence(web_data, resolution_url)

        # Gate 3 — evidence is relevant
        evidence_reason = self._gate_relevance(question, web_data)

        # All gates passed — AI interprets verified evidence
        final = self._multi_ai_resolve(question, web_data, "Resolution — all truth gates passed")

        market.update({
            "status":         "resolved",
            "outcome":        final["outcome"],
            "reasoning":      final["reasoning"],
            "confidence":     final["confidence"],
            "votes":          final["votes"],
            "data_source":    "web_verified",
            "evidence_reason": evidence_reason,
            "resolved_at_tx": self._next_tx(),
            "resolver":       resolver_id,
            "is_final":       True,
        })
        self.markets[market_id] = json.dumps(market)

    @gl.public.write
    def claim_winnings(self, market_id: str, bet_id: str) -> str:
        self._check_not_paused()

        if market_id not in self.markets:
            raise Exception("Market not found")
        if bet_id not in self.bets:
            raise Exception("Bet not found")

        market = json.loads(self.markets[market_id])
        bet    = json.loads(self.bets[bet_id])

        if market["status"] != "resolved":
            raise Exception("Market is not resolved yet")
        if bet["claimed"]:
            raise Exception("Winnings already claimed")
        if bet["market_id"] != market_id:
            raise Exception("Bet does not belong to this market")

        self._acquire_claim_lock(bet_id)
        winnings = "0"
        try:
            bet = json.loads(self.bets[bet_id])
            if bet["side"] == market["outcome"]:
                winning_pool = market["yes_pool"] if market["outcome"] == "YES" else market["no_pool"]
                losing_pool  = market["no_pool"]  if market["outcome"] == "YES" else market["yes_pool"]
                if winning_pool > 0:
                    bet_amount = bet["amount"]
                    payout     = bet_amount + (bet_amount * losing_pool // winning_pool)
                    self._add_to_balance(bet["bettor"], payout)
                    winnings = str(payout)
            bet = json.loads(self.bets[bet_id])
            bet["claimed"] = True
            self.bets[bet_id] = json.dumps(bet)
        finally:
            self._release_claim_lock(bet_id)

        return winnings

    @gl.public.write
    def appeal_market(self, market_id: str, reason: str, appealer_id: str) -> None:
        self._check_not_paused()

        if market_id not in self.markets:
            raise Exception("Market not found")

        market = json.loads(self.markets[market_id])

        if market.get("is_final") and market["appeal_count"] >= 2:
            raise Exception("Market is permanently finalized — no more appeals")
        if market["status"] != "resolved":
            raise Exception("Only resolved markets can be appealed")
        if market["appeal_count"] >= 2:
            raise Exception("Maximum 2 appeals allowed")
        if not (10 <= len(reason) <= 500):
            raise Exception("Appeal reason must be 10–500 characters")

        if int(self.tx_counter) < market.get("last_appeal_tx", 0) + 3:
            raise Exception("Appeal cooldown — wait a few transactions")

        self._greybox(reason, "appeal reason")

        if self._incr(self.address_appeal_count, appealer_id) > MAX_APPEALS_PER_ADDRESS:
            raise Exception(f"Max {MAX_APPEALS_PER_ADDRESS} appeals per address")

        appealer_bal = int(self.balances[appealer_id]) if appealer_id in self.balances else 0
        if appealer_bal < APPEAL_FEE:
            raise Exception(f"Need {APPEAL_FEE} for appeal fee (balance: {appealer_bal})")

        self.balances[appealer_id] = str(appealer_bal - APPEAL_FEE)
        self._add_to_platform(APPEAL_FEE)

        appeal_id = f"{market_id}_appeal_{market['appeal_count'] + 1}"
        if appeal_id in self.appeal_requests:
            raise Exception("Appeal already submitted")

        self.appeal_requests[appeal_id] = json.dumps({
            "market_id":       market_id,
            "reason":          reason,
            "original_outcome": market["outcome"],
            "appeal_number":   market["appeal_count"] + 1,
            "appealer":        appealer_id,
            "appeal_fee_paid": APPEAL_FEE,
            "appealed_at_tx":  int(self.tx_counter),
        })

        context = (
            f"APPEAL #{market['appeal_count'] + 1}\n"
            f"Original outcome:  {market['outcome']}\n"
            f"Original reasoning: {market['reasoning']}\n"
            f"Appeal reason:     {reason}\n"
            "Re-evaluate carefully using evidence below."
        )

        # Re-fetch evidence; if unavailable fall back to reasoning-only re-evaluation
        web_data = self._fetch_url(market.get("resolution_url", ""))
        if len(web_data.strip()) >= MIN_EVIDENCE_LENGTH:
            self._gate_relevance(market["question"], web_data)
            final = self._multi_ai_resolve(market["question"], web_data, context)
        else:
            final = self._multi_ai_resolve(market["question"], "", context)

        # Slash original resolver if outcome flipped
        if final["outcome"] != market["outcome"]:
            resolver = market.get("resolver", "")
            if resolver and resolver in self.stakes:
                resolver_stake = int(self.stakes[resolver])
                slash          = (resolver_stake * SLASH_PERCENT_ON_OVERRIDE) // 100
                self.stakes[resolver] = str(max(0, resolver_stake - slash))
                self._add_to_platform(slash)

        market.update({
            "outcome":        final["outcome"],
            "reasoning":      final["reasoning"],
            "votes":          final["votes"],
            "appeal_count":   market["appeal_count"] + 1,
            "last_appeal_tx": self._next_tx(),
            "status":         "resolved",
            "is_final":       market["appeal_count"] + 1 >= 2,
        })
        self.markets[market_id] = json.dumps(market)

    @gl.public.write
    def cancel_market(self, market_id: str) -> None:
        self._check_not_paused()
        if market_id not in self.markets:
            raise Exception("Market not found")
        market = json.loads(self.markets[market_id])
        if market["status"] != "open":
            raise Exception("Only open markets can be cancelled")
        market["is_cancelled"] = True
        market["status"]       = "cancelled"
        self.markets[market_id] = json.dumps(market)

    @gl.public.write
    def refund_bet(self, market_id: str, bet_id: str) -> str:
        if market_id not in self.markets:
            raise Exception("Market not found")
        if bet_id not in self.bets:
            raise Exception("Bet not found")

        market = json.loads(self.markets[market_id])
        bet    = json.loads(self.bets[bet_id])

        if not market.get("is_cancelled"):
            raise Exception("Market is not cancelled")
        if bet.get("refunded"):
            raise Exception("Already refunded")
        if bet["market_id"] != market_id:
            raise Exception("Bet does not belong to this market")

        self._add_to_balance(bet["bettor"], bet["gross_amount"])
        bet["refunded"] = True
        self.bets[bet_id] = json.dumps(bet)
        return str(bet["gross_amount"])

    @gl.public.write
    def withdraw(self, user: str) -> str:
        if user not in self.balances:
            raise Exception("No balance found")
        balance = int(self.balances[user])
        if balance <= 0:
            raise Exception("Balance is zero")
        self.balances[user] = "0"
        return str(balance)

    @gl.public.write
    def withdraw_platform_fees(self) -> str:
        bal = int(self.balances["platform"]) if "platform" in self.balances else 0
        if bal <= 0:
            raise Exception("No platform fees to withdraw")
        self.balances["platform"] = "0"
        return str(bal)

    # ════════════════════════════════════════════════════════════════════════
    # PUBLIC VIEW METHODS
    # ════════════════════════════════════════════════════════════════════════

    @gl.public.view
    def get_market(self, market_id: str) -> str:
        if market_id not in self.markets:
            return '{"error": "Market not found"}'
        return self.markets[market_id]

    @gl.public.view
    def get_bet(self, bet_id: str) -> str:
        if bet_id not in self.bets:
            return '{"error": "Bet not found"}'
        return self.bets[bet_id]

    @gl.public.view
    def get_appeal(self, appeal_id: str) -> str:
        if appeal_id not in self.appeal_requests:
            return '{"error": "Appeal not found"}'
        return self.appeal_requests[appeal_id]

    @gl.public.view
    def get_balance(self, user: str) -> str:
        return self.balances[user] if user in self.balances else "0"

    @gl.public.view
    def get_resolver_stake(self, addr: str) -> str:
        return self.stakes[addr] if addr in self.stakes else "0"

    @gl.public.view
    def get_contract_status(self) -> str:
        return json.dumps({
            "version":                        VERSION,
            "owner":                          self.owner,
            "auto_resolver":                  self.auto_resolver,
            "paused":                         self.paused,
            "tx_counter":                     self.tx_counter,
            "min_bet":                        MIN_BET,
            "max_bet":                        MAX_BET,
            "platform_fee_percent":           PLATFORM_FEE_PERCENT,
            "appeal_fee":                     APPEAL_FEE,
            "ai_consensus_threshold":         AI_CONSENSUS_THRESHOLD,
            "ai_model_count":                 AI_MODEL_COUNT,
            "resolver_stake_required":        RESOLVER_STAKE_REQUIRED,
            "slash_percent_on_override":      SLASH_PERCENT_ON_OVERRIDE,
            "min_evidence_length":            MIN_EVIDENCE_LENGTH,
            "max_bets_per_market":            MAX_BETS_PER_MARKET,
            "max_bets_per_address_per_market": MAX_BETS_PER_ADDRESS_PER_MARKET,
            "max_markets_per_address":        MAX_MARKETS_PER_ADDRESS,
            "max_appeals_per_address":        MAX_APPEALS_PER_ADDRESS,
            "truth_gates":                    ["deadline", "evidence", "relevance"],
        })

    @gl.public.view
    def get_market_summary(self, market_id: str) -> str:
        if market_id not in self.markets:
            return '{"error": "Market not found"}'
        m     = json.loads(self.markets[market_id])
        total = m["yes_pool"] + m["no_pool"]
        yes_pct = (m["yes_pool"] * 100 // total) if total > 0 else 0
        return json.dumps({
            "version":              m.get("version", VERSION),
            "question":             m["question"],
            "status":               m["status"],
            "is_final":             m.get("is_final", False),
            "is_cancelled":         m.get("is_cancelled", False),
            "outcome":              m["outcome"],
            "votes":                m.get("votes", {}),
            "yes_pool":             m["yes_pool"],
            "no_pool":              m["no_pool"],
            "yes_percent":          yes_pct,
            "no_percent":           100 - yes_pct if total > 0 else 0,
            "total_pool":           total,
            "fees_collected":       m["total_fees_collected"],
            "bet_count":            m.get("bet_count", 0),
            "appeal_count":         m["appeal_count"],
            "confidence":           m.get("confidence", "unknown"),
            "data_source":          m.get("data_source", "unknown"),
            "reasoning":            m.get("reasoning", ""),
            "evidence_reason":      m.get("evidence_reason", ""),
            "resolver":             m.get("resolver", ""),
            "deadline_str":         m.get("deadline_str", ""),
            "deadline_iso":         m.get("deadline_iso", ""),
            "resolution_url":       m.get("resolution_url", ""),
            "creator":              m.get("creator", "unknown"),
            "created_at_tx":        m.get("created_at_tx", 0),
            "resolved_at_tx":       m.get("resolved_at_tx", 0),
            "ai_validation_passed": m.get("ai_validation_passed", True),
            "ai_validation_reason": m.get("ai_validation_reason", ""),
        })

    @gl.public.view
    def get_ai_commentary(self, market_id: str) -> str:
        if market_id not in self.markets:
            return '{"error": "Market not found"}'
        m     = json.loads(self.markets[market_id])
        total = m["yes_pool"] + m["no_pool"]
        if total == 0:
            return json.dumps({"commentary": "No bets placed yet.", "sentiment": "neutral"})

        yes_pct = m["yes_pool"] * 100 // total
        no_pct  = 100 - yes_pct

        def get_commentary() -> typing.Any:
            task = f"""Prediction market analyst. Summarise in 2 sentences.
Question: {m['question']}
YES {yes_pct}% / NO {no_pct}% | bets: {m.get('bet_count', 0)} | status: {m['status']}
Return ONLY JSON:
{{"commentary": "2 sentences", "sentiment": "bullish_yes|bullish_no|neutral|contested"}}"""
            result = gl.nondet.exec_prompt(task, response_format="json")
            if not isinstance(result, dict):
                raise Exception("Commentary: bad response")
            sentiment = result.get("sentiment", "neutral")
            if sentiment not in ["bullish_yes", "bullish_no", "neutral", "contested"]:
                sentiment = "neutral"
            return {"commentary": str(result.get("commentary", "")), "sentiment": sentiment}

        result = gl.vm.run_nondet_unsafe(
            get_commentary,
            lambda res: isinstance(res, gl.vm.Return)
                        and isinstance(res.calldata, dict)
                        and len(res.calldata.get("commentary", "")) >= 10,
        )
        return json.dumps({
            "market_id":   market_id,
            "commentary":  result["commentary"],
            "sentiment":   result["sentiment"],
            "yes_percent": yes_pct,
            "no_percent":  no_pct,
            "total_pool":  total,
        })