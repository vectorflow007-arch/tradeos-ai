<p align="center">
  <img src="https://img.shields.io/badge/TradeOS-India-007acc?style=for-the-badge&labelColor=1a1d23&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMDA3YWNjIiBzdHJva2Utd2lkdGg9IjIiPjxwb2x5bGluZSBwb2ludHM9IjMsMTggNyw4IDEyLDE0IDE3LDQgMjEsMTAiLz48L3N2Zz4=" alt="TradeOS India"/>
</p>

<h1 align="center">TradeOS India</h1>

<p align="center">
  <strong>Autonomous AI-Powered Trading Desktop for Indian Markets</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/PySide6-Qt%206-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PySide6"/>
  <img src="https://img.shields.io/badge/Claude-Sonnet-cc785c?style=flat-square&logo=anthropic&logoColor=white" alt="Claude"/>
  <img src="https://img.shields.io/badge/GPT--4o-OpenAI-412991?style=flat-square&logo=openai&logoColor=white" alt="OpenAI"/>
  <img src="https://img.shields.io/badge/Groq-Llama%203.1-f55036?style=flat-square" alt="Groq"/>
  <img src="https://img.shields.io/badge/Fyers-v3%20API-00c853?style=flat-square" alt="Fyers"/>
  <img src="https://img.shields.io/badge/tests-104%20passed-4ec9b0?style=flat-square" alt="Tests"/>
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License"/>
</p>

<p align="center">
  A production-grade PySide6 desktop application for Indian retail traders across<br/>
  <strong>NSE</strong> &bull; <strong>BSE</strong> &bull; <strong>NFO</strong> &bull; <strong>MCX</strong> &bull; <strong>CDS</strong><br/>
  Combining LLM-powered autonomous agents with real-time market data,<br/>
  risk management, and broker integration in a sleek VS Code-inspired interface.
</p>

---

## Highlights

```
 4 Autonomous AI Agents      Multi-Provider LLM System      Fyers v3 Broker Integration
 Real-Time WebSocket Feed    Circuit Breaker Risk Engine     Paper + Live Trading Modes
 VS Code-Inspired HTML UI    104 Pytest Test Suite           OS Keyring Security
```

---

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
  - [Autonomous Agent System](#-autonomous-agent-system)
  - [Multi-Provider LLM](#-multi-provider-llm-system)
  - [Broker Integration](#-broker-integration-fyers-v3)
  - [Data Pipeline](#-real-time-data-pipeline)
  - [Risk Management](#-risk-management)
  - [User Interface](#-vs-code-inspired-html-ui)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Database Schema](#database-schema)
- [Testing](#testing)
- [Supported Markets](#supported-markets)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Architecture

```
tradeOS_india/
 |
 |-- main.py                          Entry point & app controller
 |
 |-- assets/
 |   |-- shell.html                   Full app UI (HTML/CSS/JS shell)
 |   |-- wizard/
 |       |-- setup_wizard.html        4-step onboarding wizard
 |       |-- settings.html            Settings panel (wizard-style)
 |       |-- monitor.html             Live trading monitor
 |
 |-- config/
 |   |-- settings.py                  Pydantic BaseSettings (env + .env)
 |   |-- constants.py                 Exchange codes, timeframes, Fyers maps
 |
 |-- core/
 |   |-- event_bus.py                 Singleton QObject with 30+ Qt signals
 |   |-- state_store.py               Pydantic AppState persisted to JSON
 |   |-- worker.py                    BaseWorker QThread + asyncio bridge
 |
 |-- utils/
 |   |-- logger.py                    Loguru IST-timestamped rotating logs
 |   |-- keychain.py                  OS keyring wrapper (zero plaintext)
 |   |-- date_utils.py                IST helpers, market hours detection
 |
 |-- storage/
 |   |-- db.py                        aiosqlite async layer (7 tables)
 |   |-- cache.py                     Polars parquet cache (contracts + candles)
 |
 |-- brokers/
 |   |-- base_broker.py               Abstract broker: 15 methods + dataclasses
 |   |-- fyers/
 |       |-- auth.py                  OAuth2 flow with local FastAPI callback
 |       |-- contracts.py             Master contracts + parquet caching
 |       |-- feed.py                  WebSocket ticks + auto-reconnect
 |       |-- orders.py                Paper simulation + live order mgmt
 |       |-- client.py                FyersClient composing all sub-modules
 |
 |-- llm/
 |   |-- base_llm.py                  Abstract LLM: complete() + stream()
 |   |-- claude_client.py             Claude Sonnet (0.90 INR/1K tokens)
 |   |-- openai_client.py             GPT-4o (1.10 INR/1K tokens)
 |   |-- groq_client.py               Llama 3.1 70B (0.05 INR/1K tokens)
 |
 |-- data/
 |   |-- market_state.py              Thread-safe singleton (ticks + Polars)
 |   |-- candle_builder.py            Tick-to-OHLCV (1m/5m/15m/1h/1D)
 |   |-- feed_router.py               Tick fanout to N subscribers
 |
 |-- agents/
 |   |-- base_agent.py                Abstract agent + task/result models
 |   |-- strategy_agent.py            LLM signal generation (BUY/SELL/HOLD)
 |   |-- risk_agent.py                LLM + deterministic risk validation
 |   |-- execution_agent.py           Order placement with paper-mode safety
 |   |-- research_agent.py            Backtest analysis via LLM
 |   |-- orchestrator.py              Priority queue + market-hours LLM selection
 |
 |-- ui/
 |   |-- theme.py                     QSS dark/light theme system
 |   |-- main_window.py               Frameless shell: TitleBar + QWebEngineView
 |   |-- screens/                     Legacy screen modules (kept for reference)
 |
 |-- tests/                           104 pytest tests across all modules
 |-- logs/                            Auto-rotating IST-timestamped logs
```

### System Flow

```
                          +-------------------+
                          |   QWebEngineView  |
                          |   (shell.html)    |
                          +--------+----------+
                                   |
                            QWebChannel
                                   |
                          +--------v----------+
                          |    ShellBridge    |
                          |    (Python)       |
                          +--------+----------+
                                   |
              +--------------------+--------------------+
              |                    |                    |
     +--------v------+   +--------v------+   +--------v------+
     |  EventBus     |   |  AppState     |   |  Orchestrator |
     |  (30+ signals)|   |  (JSON store) |   |  (agent mgr)  |
     +--------+------+   +---------------+   +--------+------+
              |                                        |
    +---------+---------+              +---------------+---------------+
    |         |         |              |         |         |           |
 +--v--+  +--v--+  +---v--+      +----v---+ +---v---+ +---v----+ +---v-----+
 |Feed |  |Data |  |Broker|      |Strategy| | Risk  | |Execute | |Research |
 |Route|  |Pipe |  |Client|      | Agent  | | Agent | | Agent  | | Agent   |
 +-----+  +-----+  +------+      +--------+ +-------+ +--------+ +---------+
```

---

## Features

### 🤖 Autonomous Agent System

Four specialized AI agents work in concert, managed by a priority-based orchestrator:

| Agent | Role | Key Capabilities |
|-------|------|-----------------|
| **Strategy** | Signal Generation | Analyzes market data via LLM, outputs BUY/SELL/HOLD with confidence scores |
| **Risk** | Pre-Trade Validation | Deterministic rules (circuit breaker, position limits, daily loss) + LLM risk scoring |
| **Execution** | Order Management | Paper mode with realistic slippage simulation; live mode via Fyers API |
| **Research** | Analysis & Backtesting | Monte Carlo simulation, strategy performance analysis via LLM |

The **Orchestrator** manages all agents through an async priority queue with intelligent LLM selection:
- Market hours (9:15-15:30 IST) → Claude Sonnet (highest quality)
- Off-hours / budget mode → Groq Llama 3.1 70B (99.5% cost reduction)

---

### 🧠 Multi-Provider LLM System

Seamlessly switch between three LLM providers with automatic failover:

| Provider | Model | Cost (INR/1K tokens) | Latency | Best For |
|----------|-------|:--------------------:|:-------:|----------|
| **Anthropic** | claude-sonnet-4-6 | 0.90 | ~1.2s | Primary analysis, signal generation |
| **OpenAI** | gpt-4o | 1.10 | ~0.9s | Fallback, alternative perspective |
| **Groq** | llama-3.1-70b | 0.05 | ~0.3s | Overnight research, budget mode |

- Token usage tracking with daily cost monitoring (INR)
- Per-request audit trail stored in SQLite
- Hot-swap between providers without restart

---

### 📡 Broker Integration (Fyers v3)

Full-featured integration with Fyers broker API:

- **OAuth2 Authentication** — Local FastAPI callback server, token persistence in OS keyring
- **Real-Time Feed** — WebSocket tick stream with exponential backoff reconnect (max 5 retries)
- **Master Contracts** — Daily download with Polars parquet caching (~50MB compressed)
- **Paper Mode** — Simulated order fills with configurable slippage (0-0.02% random)
- **Live Mode** — Full order lifecycle: place → status poll → modify → cancel
- **Position Tracking** — Real-time P&L calculation across all open positions

---

### 📊 Real-Time Data Pipeline

```
Tick Stream → FeedRouter → CandleBuilder → MarketState → Agents
                              |
                    5 Timeframes: 1m, 5m, 15m, 1h, 1D
                              |
                    Polars DataFrames (columnar, fast)
```

- Thread-safe `MarketState` singleton with concurrent read/write
- Polars-powered candle aggregation (10x faster than pandas)
- Parquet caching for historical data and contract masters
- Fan-out architecture: single feed, unlimited subscribers

---

### 🛡️ Risk Management

Multi-layered risk engine with real-time monitoring:

| Control | Description | Default |
|---------|-------------|:-------:|
| **Daily Loss Limit** | Hard cap on total daily loss (INR) | 5,000 |
| **Per-Trade Risk** | Maximum risk as % of capital per trade | 1.0% |
| **Max Positions** | Maximum concurrent open positions | 5 |
| **Stop-Loss Cap** | Maximum stop-loss distance | 2.0% |
| **Circuit Breaker** | Auto-pause all trading at loss threshold | 80% |
| **Kill Switch** | Emergency stop: cancel all orders, close all positions | Manual |

Every order passes through the Risk Agent before execution. No exceptions.

---

### 🎨 VS Code-Inspired HTML UI

The entire application interface is rendered as a polished HTML/CSS/JS shell inside `QWebEngineView`, delivering a modern web-app experience in a native desktop wrapper:

**Layout:**
- **Activity Bar** — SVG icon navigation (6 screens + settings)
- **Sidebar** — Collapsible panel with watchlist and screen navigation
- **Tab Bar** — Tabbed editor-style screen switching
- **Editor Area** — 5 full-screen panels with rich content
- **Bottom Panel** — Terminal, Problems, Output, Agent Feed tabs
- **Status Bar** — Mode, broker status, LLM, clock, market state

**Screens:**

| Screen | Contents |
|--------|----------|
| **Live Monitor** | Real-time stats (P&L, trades, win rate, tokens), 4 agent cards, activity log, risk gauge |
| **Strategy Builder** | Code editor with strategy templates, timeframe selector, signal preview pane |
| **Backtest** | 6 metric cards (return, win rate, Sharpe, drawdown, trades, profit factor), equity curve area |
| **Agent Log** | Per-agent status cards with task/token/cost metrics, live agent log feed |
| **Risk Monitor** | 6 risk metric cards, risk event log, loss gauge with daily limit tracking |

**Bridge Architecture:**
- `QWebChannel` connects JS ↔ Python bidirectionally
- `ShellBridge` exposes Python state and actions to the HTML shell
- `SettingsBridge` powers the settings wizard panel
- Real-time data push from Python agents into the HTML UI

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Desktop Framework | **PySide6** (Qt 6) | Native performance, cross-platform |
| UI Rendering | **QWebEngineView** + HTML/CSS/JS | Modern web-quality visuals |
| Bridge | **QWebChannel** | Bidirectional Python ↔ JS communication |
| Async Database | **aiosqlite** | Non-blocking SQLite with 7 tables |
| Data Processing | **Polars** | Columnar DataFrame, 10x faster than pandas |
| Broker API | **Fyers v3** | REST + WebSocket for Indian markets |
| LLM Providers | **Anthropic, OpenAI, Groq** | Multi-model AI with cost optimization |
| Auth Server | **FastAPI** | Local OAuth2 callback (ephemeral) |
| Configuration | **Pydantic** BaseSettings | Type-safe config with env var support |
| Secrets | **OS Keyring** | Zero plaintext credential storage |
| Logging | **Loguru** | IST timestamps, rotating files, structured output |
| Testing | **Pytest** | 104 tests, all passing |

---

## Getting Started

### Prerequisites

- Python 3.12+
- Windows 10/11 (primary), macOS / Linux supported
- Fyers trading account (for broker features)
- At least one LLM API key (Claude, OpenAI, or Groq)

### Installation

```bash
# Clone
git clone https://github.com/vectorflow007-arch/tradeos-ai.git
cd tradeos-ai

# Install dependencies
pip install -r tradeOS_india/requirements.txt

# Launch
cd tradeOS_india
python main.py
```

### First Run

On first launch, a **4-step setup wizard** guides you through:

| Step | Configuration |
|:----:|--------------|
| **1** | Trading mode (Paper/Live), market segments, daily loss limit |
| **2** | Fyers API credentials and connection test |
| **3** | LLM provider selection, agent enable/disable toggles |
| **4** | Summary review and launch confirmation |

All credentials are stored in your OS keyring — never in config files.

---

## Configuration

### Environment Variables

Override any setting with the `TRADEOS_` prefix:

```bash
TRADEOS_MODE=paper              # paper | live
TRADEOS_BROKER=fyers            # Broker name
TRADEOS_LLM_PRIMARY=claude      # claude | openai | groq
TRADEOS_DAILY_LOSS_LIMIT=5000   # INR
TRADEOS_THEME=dark              # dark | light
```

Or place a `.env` file in the `tradeOS_india/` directory.

### API Keys (OS Keyring)

| Service | Keys Required |
|---------|--------------|
| **Fyers** | App ID, Secret Key, PIN |
| **Anthropic** | API key |
| **OpenAI** | API key |
| **Groq** | API key |

Keys are set during the setup wizard and stored securely in your operating system's credential manager.

---

## Database Schema

Seven tables managed by aiosqlite:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `trades` | Full trade lifecycle | symbol, side, price, qty, pnl, mode |
| `daily_summary` | Aggregated daily metrics | date, total_pnl, trade_count, win_rate |
| `agent_logs` | Agent task execution history | agent, task_type, status, duration_ms |
| `llm_messages` | LLM request/response audit | provider, model, tokens, cost_inr |
| `strategies` | Saved strategy definitions | name, rules_json, created_at |
| `settings` | Key-value app settings | key, value, updated_at |
| `watchlist` | User's tracked symbols | symbol, exchange, added_at |

---

## Testing

```bash
cd tradeOS_india
python -m pytest tests/ -v
```

```
========================= 104 passed in 6.88s =========================
```

### Test Coverage Breakdown

| Module | Tests | Coverage |
|--------|:-----:|----------|
| Utils (logger, keychain, date_utils) | 15 | Core utilities and IST time handling |
| Config (settings, constants) | 11 | Settings validation, exchange mappings |
| Core (event_bus, state_store) | 10 | Signal system, state persistence |
| Storage (db, cache) | 8 | SQLite operations, parquet caching |
| Brokers (base, Fyers modules) | 10 | Auth flow, order simulation, feed |
| LLM (base, 3 providers) | 6 | Provider abstraction, token counting |
| Data (market_state, candle_builder, feed_router) | 10 | Tick processing, candle aggregation |
| Agents (base, 4 agents, orchestrator) | 8 | Task lifecycle, priority queue |
| UI (theme, main_window, bridges, screens) | 26 | Theme system, bridge communication |

---

## Supported Markets

| Exchange | Segment | Description | Trading Hours (IST) |
|:--------:|:-------:|-------------|:-------------------:|
| **NSE** | Equity | National Stock Exchange | 09:15 - 15:30 |
| **BSE** | Equity | Bombay Stock Exchange | 09:15 - 15:30 |
| **NFO** | F&O | NSE Futures & Options | 09:15 - 15:30 |
| **MCX** | Commodity | Multi Commodity Exchange | 09:00 - 23:30 |
| **CDS** | Currency | Currency Derivatives | 09:00 - 17:00 |

---

## Roadmap

### Completed

- [x] **Phase 1** — Foundation (logger, keychain, date_utils, event_bus, state_store)
- [x] **Phase 2** — Storage (aiosqlite, Polars cache)
- [x] **Phase 3** — Fyers Broker (auth, contracts, feed, orders, client)
- [x] **Phase 4** — LLM Clients (Claude, OpenAI, Groq)
- [x] **Phase 5** — Data Pipeline (market_state, candle_builder, feed_router)
- [x] **Phase 6** — Agents (strategy, risk, execution, research, orchestrator)
- [x] **Phase 7** — HTML Assets (setup wizard, monitor, settings)
- [x] **Phase 8** — UI Shell (theme, main_window, VS Code layout)
- [x] **Phase 9** — UI Screens (6 screen modules)
- [x] **Phase 10** — Integration (main.py controller)
- [x] **Phase 11** — Testing (104 pytest tests)
- [x] **Phase 12** — Documentation & GitHub
- [x] **Phase 13** — Full HTML UI Overhaul (shell.html, QWebEngineView shell)

### Planned

- [ ] Multi-broker support (Zerodha Kite, Angel One SmartAPI, Upstox v2)
- [ ] Options chain analytics with Greeks calculation
- [ ] Strategy marketplace with community sharing
- [ ] Advanced charting with TradingView lightweight-charts
- [ ] Mobile companion app (React Native)
- [ ] Cloud sync for settings, strategies, and trade history
- [ ] Portfolio analytics with sector/market-cap breakdown
- [ ] Webhook alerts (Telegram, Discord, Email)

---

## Security

| Concern | Approach |
|---------|----------|
| API credentials | OS keyring (never in config/logs/state files) |
| Trading mode | Paper mode enforced by default; live requires explicit opt-in |
| Pre-trade validation | Every order validated by Risk Agent before execution |
| LLM audit trail | All LLM calls logged with tokens, cost, and response |
| State persistence | Non-sensitive state only; secrets excluded from JSON |

---

## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

For major changes, please open an issue first to discuss what you'd like to change.

---

## License

This project is provided for **educational and research purposes**. Trading in financial markets involves substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.

---

<p align="center">
  <sub>Built with <a href="https://claude.ai">Claude Code</a> by Anthropic</sub>
</p>
