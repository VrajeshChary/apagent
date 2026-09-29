# VALKYRIE // AP-77 (LEDGERWERK-77)
### Autonomous Accounts Payable Exception Resolution Agent & Tactical Command Matrix

VALKYRIE // AP-77 is an autonomous Accounts Payable (AP) Exception Resolution Agent equipped with cognitive memory (**Hindsight / ChromaDB**), contractual policy audit rules, and a **Groq LLM** resolution loop (`qwen-qwq-32b`) with rule-based fallback.

It features **VALKYRIE // LEDGERWERK-77**, a tactile, non-AI looking cyber-industrial command console with real-time vector sonar radar, dot-matrix invoice voucher viewer, human signoff override desk, chaos incident injector, and procedural Web Audio DSP feedback.

---

## Key Features

- **Cognitive 3-Phase Memory Architecture (`retain`, `recall`, `reflect`)**:
  - `retain()`: Ingests vendor risk profiles, contracts, historical negotiation threads, and human approval records into vector storage.
  - `recall()`: Semantically queries nearest precedents for each detected invoice discrepancy with similarity scoring.
  - `reflect()`: Synthesizes vendor behavioral mental models, risk tiers, and auto-approval thresholds.
- **Contractual Exception Scanner**:
  - Freight & shipping term deviations (e.g. FOB Destination variance allowances vs free shipping clauses).
  - Out-of-scope line item charges & unauthorized change orders.
  - Fixed retainer overages and unauthorized hourly billing.
  - Multi-state tax discrepancies and regional exemptions.
  - Payment terms mismatches.
- **Groq AI Agent Loop**:
  - Analyzes exceptions in real time using historical memory context.
  - Automatically decides actions: `auto_approved`, `approved_with_adjustment`, `escalated_to_human`, or `rejected`.
- **VALKYRIE // LEDGERWERK-77 Console**:
  - **Tactile Hardware Chassis**: Milled gunmetal & titanium casing with Torx rivets, warning chevrons, and LED lamps.
  - **Phosphor Amber CRT Terminal**: Real scanlines, vignetting, and streaming teletype logging.
  - **Analog Galvanometer Gauges**: Damped needle physics for Peak Variance and Mean Confidence.
  - **2D Vector Radar (Canvas)**: Real rotating sweep beam with live blip echoes for approvals, contracts, and disputes.
  - **Vector Vault Probe Station**: Direct semantic query scanner with laser lock-on trace.
  - **Dot-Matrix Voucher & Dossier**: Green-bar perforated invoice slip with red felt-tip discrepancy markers and side-by-side contract policy comparison.
  - **Pneumatic Rubber Stamp Desk**: Instant human override actions with ink stamp animations.
  - **Chaos Incident Injector**: Dynamically inject real-world supply chain anomalies.
  - **Procedural Web Audio DSP**: Mechanical clicks, solenoid relay thuds, teletype ticks, sonar pings, hydraulic stamps, and alarm klaxons (zero audio files needed).

---

## Project Structure

```
invoice-agent/
├── agents/
│   ├── exception_detector.py  # Rule-based discrepancy detection engine
│   └── resolver.py            # Groq LLM agent & Hindsight recall loop
├── config/
│   └── settings.py            # API keys, thresholds, vendor risk tiers
├── data/
│   ├── chroma_db/             # Local vector database storage (gitignored)
│   └── synthetic/
│       └── generator.py       # Vendors, contracts, emails, approvals, invoices
├── hindsight/
│   ├── client.py              # ChromaDB & Hindsight vector memory client
│   ├── ingest.py              # Data ingestion pipeline (retain)
│   └── reflect_runner.py      # Vendor mental model synthesis (reflect)
├── models/
│   └── schemas.py             # Data dataclasses & Enums
├── ui/
│   ├── console.html           # Tactical command console frontend
│   ├── server.py              # Python stdlib HTTP control bridge & API
│   └── selftest.py            # End-to-end in-process integration test
├── requirements.txt           # Python dependencies
└── main.py                    # Terminal CLI entry point
```

---

## Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Create a `.env` file (optional if using rule-based fallback):
```ini
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=qwen-qwq-32b
USE_LOCAL_HINDSIGHT=true
```

### 3. Launch the Control Bridge & Frontend
```bash
python -m ui.server
```
Then open your browser at:
👉 **`http://127.0.0.1:8787/`**

### 4. Run Automated Selftest
```bash
python -m ui.selftest
```

---

## Keyboard Hotkeys (Console)

- `[1]` — **Ingest Archive** (`retain`)
- `[2]` — **Detect Exceptions** (run scanner array)
- `[3]` — **Resolve All** (engage Groq agent loop)
- `[4]` — **Reflect Profiles** (synthesize mental models)
- `[P]` — **Focus Vector Probe** (semantic search)
- `[M]` — **Toggle Mechanical Audio**
- `[Esc]` — **Close Tactical Dossier**
