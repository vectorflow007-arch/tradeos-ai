# TradeOS India

**Autonomous AI-Powered Trading Desktop Application for Indian Markets**

A production-ready PySide6 desktop application targeting Indian retail traders across NSE, BSE, NFO, MCX, and CDS segments. TradeOS India combines LLM-powered autonomous agents with real-time market data, risk management, and broker integration into a VS Code-inspired dark-themed interface.

---

## Screenshots

| Setup Wizard | Live Monitor |
|:---:|:---:|
| 4-step dark-themed wizard with broker auth, LLM config, and risk setup | Real-time dashboard with agent cards, trade log, and risk gauge |

| Strategy Builder | Agent Monitor |
|:---:|:---:|
| Code editor with strategy templates and signal preview | 4 autonomous agents with task queue and live logs |

---

## Architecture

```
tradeOS_india/
|
|-- main.py                      # Application entry point
|
|-- config/
|   |-- settings.py              # Pydantic BaseSettings (env vars, .env)
|   |-- constants.py             # Exchange codes, timeframes, Fyers maps
|
|-- core/
|   |-- event_bus.py             # Singleton QObject with 30+ Qt signals
|   |-- state_store.py           # Pydantic AppState persisted to JSON
|   |-- worker.py                # BaseWorker QThread + asyncio bridge
|
|-- utils/
|   |-- logger.py                # loguru IST-timestamped rotating logs
|   |-- keychain.py              # OS keyring wrapper (no plaintext secrets)
|   |-- date_utils.py            # IST helpers, market hours detection
|
|-- storage/
|   |-- db.py                    # aiosqlite async layer (7 tables)
|   |-- cache.py                 # Polars parquet cache (contracts + candles)
|
|-- brokers/
|   |-- base_broker.py           # Abstract broker with 15 methods + dataclasses
|   |-- fyers/
|       |-- auth.py              # OAuth2 flow with local FastAPI callback
|       |-- contracts.py         # Master contract download + parquet cache
|       |-- feed.py              # WebSocket tick feed with auto-reconnect
|       |-- orders.py            # Paper mode simulation + live order management
|       |-- client.py            # FyersClient composing all sub-modules
|
|-- llm/
|   |-- base_llm.py              # Abstract LLM with complete() + stream()
|   |-- claude_client.py         # Claude Sonnet (0.9 INR/1K tokens)
|   |-- openai_client.py         # GPT-4o (1.1 INR/1K tokens)
|   |-- groq_client.py           # Llama 3.1 70B (0.05 INR/1K tokens)
|
|-- data/
|   |-- market_state.py          # Thread-safe singleton (ticks + Polars candles)
|   |-- candle_builder.py        # Tick-to-OHLCV (1m/5m/15m/1h/1D)
|   |-- feed_router.py           # Tick fanout to subscribers
|
|-- agents/
|   |-- base_agent.py            # Abstract agent + task/result dataclasses
|   |-- strategy_agent.py        # LLM signal generation (BUY/SELL/HOLD)
|   |-- risk_agent.py            # LLM + deterministic risk validation
|   |-- execution_agent.py       # Order placement with paper mode safety
|   |-- research_agent.py        # Backtest analysis via LLM
|   |-- orchestrator.py          # Priority queue + market-hours LLM selection
|
|-- ui/
|   |-- theme.py                 # QSS dark/light theme system
|   |-- main_window.py           # VS Code shell (frameless, custom titlebar)
|   |-- screens/
|       |-- setup_wizard.py      # QWebEngineView + QWebChannel wizard
|       |-- dashboard.py         # Live monitor (HTML-based)
|       |-- strategy_builder.py  # Code editor + signal preview
|       |-- backtest_screen.py   # Metrics cards + trade log table
|       |-- agent_monitor.py     # 4 agent cards + task queue + log
|       |-- risk_monitor.py      # Risk gauge + circuit breaker log
|
|-- assets/wizard/
|   |-- setup_wizard.html        # 4-step dark-themed setup wizard
|   |-- monitor.html             # Live trading monitor with simulation
|   |-- settings.html            # Wizard-style settings panel
|
|-- tests/                       # 104 pytest tests across all modules
|-- logs/                        # Auto-rotating IST-timestamped logs
```

---

## Key Features

### Autonomous Agent System
- **Strategy Agent** -- LLM-powered signal generation with full market context
- **Risk Agent** -- Deterministic pre-validation (circuit breaker, max positions, daily loss) + LLM risk scoring
- **Execution Agent** -- Paper mode simulation with realistic slippage, live mode with Fyers API
- **Research Agent** -- Backtest analysis with Monte Carlo simulation via LLM
- **Orchestrator** -- Async priority queue, market-hours LLM selection (Claude during market, Groq overnight)

### Multi-Provider LLM System
| Provider | Model | Cost (INR/1K tokens) | Use Case |
|----------|-------|---------------------|----------|
| Claude | claude-sonnet-4-6 | 0.90 | Primary (market hours) |
| OpenAI | gpt-4o | 1.10 | Fallback |
| Groq | llama-3.1-70b | 0.05 | Overnight / budget mode |

### Broker Integration (Fyers v3)
- OAuth2 authentication with local callback server
- Real-time WebSocket tick feed with exponential backoff reconnect
- Master contract download with Polars parquet caching
- Paper mode: simulated fills with 0-0.02% random slippage
- Live mode: full order lifecycle with status polling

### Data Pipeline
- Tick-to-OHLCV candle building across 5 timeframes (1m, 5m, 15m, 1h, 1D)
- Thread-safe MarketState singleton with Polars DataFrame storage
- FeedRouter tick fanout to multiple subscribers
- Parquet caching for contracts and historical candles

### Risk Management
- Daily loss limit with real-time gauge
- Per-trade risk percentage control
- Maximum open positions limit
- Circuit breaker (auto-pause at configurable loss %)
- Kill switch (emergency stop all agents)
- Pre-trade validation before every order

### VS Code-Inspired UI
- Frameless window with custom draggable title bar
- Activity bar with QPainter-drawn icons
- Collapsible sidebar with animated transitions
- Tab bar with 5 editor screens
- Bottom panel (Terminal, Problems, Output, Agent Feed)
- Status bar with live clock, market status, broker state
- Dark and light theme with runtime switching

### Security
- All credentials stored in OS keyring (never in config files)
- Paper mode enforced by default (explicit opt-in for live trading)
- Live mode requires confirmation in setup wizard
- No plaintext secrets in logs or state files

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop Framework | PySide6 (Qt 6) |
| HTML UI Panels | QWebEngineView + QWebChannel |
| Async Database | aiosqlite (7 tables) |
| Data Processing | Polars (parquet caching) |
| Broker API | Fyers v3 (REST + WebSocket) |
| LLM Providers | Anthropic, OpenAI, Groq |
| Auth Server | FastAPI (local OAuth callback) |
| Config | Pydantic BaseSettings |
| Secrets | OS Keyring |
| Logging | Loguru (IST, rotating) |
| Testing | Pytest (104 tests) |

---

## Installation

### Prerequisites
- Python 3.12+
- Windows 10/11 (primary target), macOS/Linux supported

### Setup

```bash
# Clone the repository
git clone https://github.com/vectorflow007-arch/tradeos-ai.git
cd tradeos-ai

# Install dependencies
pip install -r tradeOS_india/requirements.txt

# Run the application
cd tradeOS_india
python main.py
```

### First Run
On first launch, the 4-step setup wizard will guide you through:

1. **Trading Mode** -- Paper (simulated) or Live, market segment selection, daily loss limit
2. **Broker Setup** -- Fyers API credentials and connection test
3. **LLM Config** -- Choose primary LLM provider, enable/disable agents
4. **Summary** -- Review all settings before launch

---

## Configuration

### Environment Variables
All settings can be overridden via environment variables with `TRADEOS_` prefix:

```bash
TRADEOS_MODE=paper
TRADEOS_BROKER=fyers
TRADEOS_LLM_PRIMARY=claude
TRADEOS_DAILY_LOSS_LIMIT=5000
TRADEOS_THEME=dark
```

Or via a `.env` file in the `tradeOS_india/` directory.

### API Keys (stored in OS keyring)
- **Fyers**: App ID, Secret Key, PIN
- **Claude**: Anthropic API key
- **OpenAI**: OpenAI API key
- **Groq**: Groq API key

---

## Database Schema

7 tables managed by aiosqlite:

| Table | Purpose |
|-------|---------|
| `trades` | Full trade lifecycle (entry, exit, P&L, mode) |
| `daily_summary` | Aggregated daily P&L and trade counts |
| `agent_logs` | Agent task execution history |
| `llm_messages` | LLM request/response audit trail |
| `strategies` | Saved strategy definitions |
| `settings` | Key-value app settings |
| `watchlist` | User's tracked symbols |

---

## Running Tests

```bash
cd tradeOS_india
python -m pytest tests/ -v
```

```
104 passed in 6.88s
```

Test coverage includes:
- Utils (logger, keychain, date_utils) -- 15 tests
- Config (settings, constants) -- 11 tests
- Core (event_bus, state_store) -- 10 tests
- Storage (db, cache) -- 8 tests
- Brokers (base, Fyers modules) -- 10 tests
- LLM (base, 3 providers) -- 6 tests
- Data pipeline (market_state, candle_builder, feed_router) -- 10 tests
- Agents (base, 4 agents, orchestrator) -- 8 tests
- UI (theme, main_window, 6 screens, full app) -- 26 tests

---

## Supported Markets

| Exchange | Segment | Description |
|----------|---------|-------------|
| NSE | Equity | National Stock Exchange |
| BSE | Equity | Bombay Stock Exchange |
| NFO | F&O | NSE Futures & Options |
| MCX | Commodity | Multi Commodity Exchange |
| CDS | Currency | Currency Derivatives |

---

## Project Roadmap

- [x] Phase 1: Foundation (logger, keychain, date_utils, event_bus, state_store)
- [x] Phase 2: Storage (aiosqlite, Polars cache)
- [x] Phase 3: Fyers Broker (auth, contracts, feed, orders, client)
- [x] Phase 4: LLM Clients (Claude, OpenAI, Groq)
- [x] Phase 5: Data Pipeline (market_state, candle_builder, feed_router)
- [x] Phase 6: Agents (strategy, risk, execution, research, orchestrator)
- [x] Phase 7: HTML Assets (setup wizard, monitor, settings)
- [x] Phase 8: UI Shell (theme, main_window, VS Code layout)
- [x] Phase 9: UI Screens (6 screen modules)
- [x] Phase 10: Integration (main.py)
- [x] Phase 11: Tests (104 pytest tests)
- [x] Phase 12: Documentation
- [ ] Multi-broker support (Zerodha, Angel One, Upstox)
- [ ] Strategy marketplace
- [ ] Mobile companion app
- [ ] Cloud sync for settings/strategies

---

## License

This project is for educational and research purposes. Use at your own risk. Trading in financial markets involves substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.

---

## Contributing

Contributions are welcome! Please open an issue first to discuss what you would like to change.

---

Built with Claude Code by Anthropic
