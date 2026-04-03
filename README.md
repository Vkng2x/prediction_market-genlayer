# TruthMarket
**AI-Powered Prediction Market on GenLayer**

TruthMarket is an Intelligent Contract that lets anyone create and bet on
real-world YES/NO prediction markets. Outcomes are resolved automatically
by AI validators using verified web evidence — no oracles, no humans needed.

---

## Deployment
| | |
|---|---|
| **Network** | GenLayer Testnet Bradbury |
| **Contract** | `0x01f0321395A7911130d9e5eE9F6B6CAE67c591CB` |
| **Wallet** | `0x93476E8BcCA792C2E17707a8096176DD6d09153E` |
| **Tx Hash** | `0x828b314f34b6b52e509649e68c3cc99a5d72f6e01599266a1182873c31fe9c34` |

---

## How It Works
Before any AI vote can happen, three Truth Gates must pass:

1. **Deadline Gate** — Market deadline must have passed
2. **Evidence Gate** — Resolution URL must return real content
3. **Relevance Gate** — AI confirms the page actually answers the question

Once all gates pass, AI validators reach consensus on YES or NO.

---

## GenLayer Integration

**Optimistic Democracy**
Validators independently run AI models and vote on outcomes.
Requires 2 of 3 to agree before the result is finalized.

**Equivalence Principle**
Every non-deterministic call includes a strict validation function
defining acceptable outputs — ensuring consistency across all validators.

---

## Full Feature List

### Market Management
- Create prediction markets with any YES/NO question
- Set custom deadlines and resolution URLs
- Cancel markets if needed
- Max 20 markets per address

### Betting System
- Bet YES or NO on any market
- Bet amount: 10 to 10,000 GEN
- Max 3 bets per address per market
- Max 100 bets per market
- 2% platform fee on every bet

### Truth Gate Resolution
- Gate 1 — Deadline must have passed (UTC clock check)
- Gate 2 — Resolution URL must return 300+ characters of real content
- Gate 3 — AI confirms the page actually answers the question
- All 3 gates must pass before AI can vote

### AI Consensus
- 3 independent AI models vote on outcome
- 2 of 3 must agree before finalizing
- Returns YES or NO with reasoning and confidence level

### Resolver Staking
- Resolver must deposit 50 GEN before resolving
- Stake slashed 50% if appeal overturns their decision

### Appeal System
- Maximum 2 appeals per market
- Costs 50 GEN to appeal
- Re-fetches evidence and re-runs AI consensus
- Market becomes final after 2nd appeal

### Winnings & Payouts
- Winners get bet back plus share of losing pool
- Re-entrancy lock prevents double claiming
- Refunds available if market is cancelled

### Security
- Prompt injection protection via greyboxing
- Re-entrancy locks on all financial operations
- HTTPS-only resolution URLs
- Emergency pause/unpause by owner

### Platform
- 2% platform fee on all bets
- Platform fee withdrawal
- Contract version tracking (v4.1.0)
- Transaction counter for audit trail

---

## Smart Contract Methods

### Read Methods

| Method | Description |
|---|---|
| `get_market` | Get raw market data |
| `get_market_summary` | Get market stats and outcome |
| `get_bet` | Get bet details by bet ID |
| `get_appeal` | Get appeal details by appeal ID |
| `get_balance` | Get balance of any address |
| `get_resolver_stake` | Get resolver stake amount |
| `get_contract_status` | Get full contract configuration |
| `get_ai_commentary` | Get AI sentiment analysis of a market |

### Write Methods

| Method | Description |
|---|---|
| `create_market` | Create a new prediction market |
| `place_bet` | Place a YES or NO bet |
| `resolve_market` | Resolve market using Truth Gates + AI |
| `appeal_market` | Appeal a resolved market outcome |
| `claim_winnings` | Claim winnings after resolution |
| `cancel_market` | Cancel an open market |
| `refund_bet` | Refund bet from cancelled market |
| `deposit_resolver_stake` | Deposit stake to become resolver |
| `withdraw_resolver_stake` | Withdraw resolver stake |
| `withdraw` | Withdraw balance |
| `withdraw_platform_fees` | Withdraw collected platform fees |
| `emergency_pause` | Pause all contract operations |
| `emergency_unpause` | Resume contract operations |

---

## Why TruthMarket Wins

| Feature | Others | TruthMarket |
|---|---|---|
| Transparent Resolution | ❌ | ✅ |
| AI-Powered Insights | ❌ | ✅ |
| Appeal System | ❌ | ✅ |
| Permissionless Access | ❌ | ✅ |
| Resolver Staking | ❌ | ✅ |
| On-Chain Settlement | ❌ | ✅ |
| Prompt Injection Protection | ❌ | ✅ |

---

## License
MIT
