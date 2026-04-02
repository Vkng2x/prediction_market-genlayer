# prediction_market-genlayer
AI-powered prediction market on GenLayer Bradbury Testnet with Truth Gates, Optimistic Democracy and Equivalence Principle

prediction_market-genlayer is an Intelligent Contract that lets anyone create and bet on. 
Real-world YES/NO prediction markets. Outcomes are resolved automatically. 
By AI validators using verified web evidence — no oracles, no humans needed.

---

## Deployment

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

## Features
- Create markets with any verifiable YES/NO question
- Bet between 10–10,000 GEN on YES or NO
- Automatic AI resolution from verified web evidence
- Appeal system with resolver stake slashing
- Prompt injection protection via greyboxing
- Re-entrancy protection on all financial operations

---

## License
MIT
