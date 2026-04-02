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

### Test Parameters

**create_market**
- market_id: `market_001`
- question: `Will Bitcoin reach $100k by end of 2026?`
- deadline_str: `2026-12-31`
- resolution_url: `https://coinmarketcap.com/currencies/bitcoin/`

**place_bet (YES)**
- market_id: `market_001`
- bet_id: `bet_001`
- side: `YES`
- amount: `100`

**place_bet (NO)**
- market_id: `market_001`
- bet_id: `bet_002`
- side: `NO`
- amount: `100`

**deposit_resolver_stake**
- resolver_id: `resolver_001`
- amount: `50`

**resolve_market**
- market_id: `market_001`
- resolver_id: `resolver_001`

---

## License
MIT
