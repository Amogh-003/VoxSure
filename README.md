# 🎙️ VoxSure— Multi-Agent Insurance Voice Assistant

> An intelligent, voice-enabled AI assistant for HDFC insurance services, powered by **Google ADK (Agent Development Kit)**, **Gemini 2.5 Flash**, and **Twilio** — with a rich **Streamlit** dashboard for real-time chat, claim uploads, and call summaries.

---

## 🌟 Features

- 📞 **Live Voice Call Integration** via Twilio — callers interact with AI agents over a real phone call
- 🤖 **Multi-Agent Architecture** — a Coordinator routes callers to specialized sub-agents
- 🗂️ **RAG-Powered Policy Explainer** — answers policy questions using ChromaDB vector search + TF-IDF fallback over real HDFC PDF documents
- 🔍 **AI Fraud Detection** — evaluates claim legitimacy using rule-based heuristics
- 📄 **Document OCR with Gemini Vision** — extracts structured data from uploaded medical bills or discharge summaries
- 💬 **Streamlit Chat Dashboard** — browser-based interface for real-time agent conversations
- 📊 **Call Summary Agent** — auto-generates post-call summaries and syncs customer data to SQLite
- 🎤 **Sentiment Analysis** — detects caller emotion to tailor responses
- 🗣️ **Google Cloud Text-to-Speech / Speech-to-Text** integration for voice I/O

---

## 🏗️ Architecture

```
Caller (Phone / Browser)
        │
        ▼
┌───────────────────────┐
│   Coordinator Agent   │  ← Master router (Gemini 2.5 Flash)
│   (coordinator.py)    │    Greets caller, identifies intent,
│                       │    and transfers to the correct sub-agent
└───────────┬───────────┘
            │
  ┌─────────┼──────────────────────────────────┐
  ▼         ▼         ▼         ▼              ▼
Policy   Policy    Claims    Renewals      Premium
Advisor  Explainer Handler   Manager       Estimator
  │         │         │
  │         │         └──► Fraud Detector Sub-Agent
  │         │
  │         └──► ChromaDB Vector DB + TF-IDF (Policy PDFs RAG)
  │
  └──► SQLite DB (Customer Profiles / Claims / Renewals)
```

---

## 🤖 Agent Descriptions

| Agent | File | Role |
|---|---|---|
| **Coordinator** | `agents/coordinator.py` | Master router — greets caller and delegates to sub-agents |
| **Policy Advisor** | `agents/advisor.py` | Collects demographics for new leads, recommends HDFC plans |
| **Policy Explainer** | `agents/explainer.py` | Answers policy document questions using RAG retrieval |
| **Claims Handler** | `agents/claims_handler.py` | Files claims, processes uploaded medical documents via Gemini Vision |
| **Fraud Detector** | `agents/fraud_subagent.py` | Evaluates claim fraud risk with rule-based heuristics |
| **Renewals Manager** | `agents/renewals_manager.py` | Checks renewal dates and processes one-click policy renewals |
| **Premium Estimator** | `agents/premium_estimator.py` | Calculates premiums, GST, and annuity/pension payouts |
| **Call Summary** | `agents/call_summary_agent.py` | Generates post-call summaries and syncs customer data to SQLite |

---

## 📂 Project Structure

```
AI voice assistant/
├── voice_server.py              # Flask server for Twilio voice webhook
├── requirements.txt             # Python dependencies
├── .env                         # API keys (not committed to git)
│
├── agents/
│   ├── coordinator.py           # Master coordinator agent
│   ├── advisor.py               # Policy advisor + lead intake
│   ├── explainer.py             # RAG-based policy explainer
│   ├── claims_handler.py        # Claims filing + Gemini Vision OCR
│   ├── fraud_subagent.py        # Fraud risk evaluator
│   ├── renewals_manager.py      # Policy renewal manager
│   ├── premium_estimator.py     # Premium & annuity calculator
│   ├── call_summary_agent.py    # Post-call summarizer & DB sync
│   └── hello_agent.py           # Simple test/demo agent
│
├── knowledge_base/
│   ├── retriever.py             # Hybrid TF-IDF + ChromaDB retriever
│   ├── policy_chunks.json       # Pre-chunked HDFC policy documents
│   ├── index_docs.py            # Script to index policy PDFs into ChromaDB
│   ├── generate_user_indexes.py # Generates per-user JSON index files
│   ├── chroma_db/               # Persistent ChromaDB vector store
│   └── user_indexes/            # Per-caller policy index cache (JSON)
│
├── data/
│   ├── db_helper.py             # SQLite CRUD helpers (lookup, save, renew, claim)
│   ├── seed_db.py               # Seeds the SQLite DB with demo customer data
│   ├── sentiment_helper.py      # Sentiment analysis utilities
│   ├── voice_helper.py          # Google Cloud TTS/STT helpers
│   ├── customers.csv            # Source customer data for seeding
│   └── insurance.db             # SQLite database (auto-created)
│
├── dashboard/
│   └── app.py                   # Streamlit web dashboard (chat UI + call summary)
│
├── tests/
│   ├── test_voice_api.py        # Voice API integration tests
│   ├── test_sentiment.py        # Sentiment analysis tests
│   ├── test_rag.py              # RAG retrieval tests
│   ├── test_transactions.py     # DB transaction tests
│   ├── test_updates.py          # Customer update tests
│   ├── test_lookups.py          # DB lookup tests
│   ├── simulate_chat.py         # End-to-end chat simulation
│   └── verify_db.py             # DB integrity verification
│
└── Dataset/                     # Source HDFC policy PDF documents
```

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.10+
- A [Google AI Studio](https://aistudio.google.com/) account for Gemini API access
- A [Twilio](https://www.twilio.com/) account (for phone call integration)
- [ngrok](https://ngrok.com/) (to expose local server for Twilio webhooks)

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd "AI voice assistant"
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
GOOGLE_APPLICATION_CREDENTIALS=path/to/google-cloud-service-account.json
```

> The `GOOGLE_APPLICATION_CREDENTIALS` is only needed if you use Google Cloud Speech-to-Text / Text-to-Speech.

### 4. Seed the Database

```bash
python data/seed_db.py
```

This creates `data/insurance.db` and populates it with demo customer profiles, policies, claim history, and renewal dates.

### 5. Index Policy Documents (for RAG)

Place your HDFC policy PDF files in the `Dataset/` folder, then run:

```bash
python knowledge_base/index_docs.py
```

This chunks the PDFs and populates the ChromaDB vector store for semantic search.

---

## 🚀 Running the Application

### Option A — Streamlit Dashboard (Chat Interface)

```bash
streamlit run dashboard/app.py
```

Open your browser at `http://localhost:8501` to interact with the AI agents via a rich chat UI.

### Option B — Twilio Voice Server (Phone Integration)

Start the Flask voice webhook server:

```bash
python voice_server.py
```

Then expose it with ngrok:

```bash
ngrok http 5000
```

Configure your Twilio phone number's **Voice Webhook** to:

```
https://<your-ngrok-url>/voice
```

Callers will now be greeted by InsureVoice AI when they dial your Twilio number.

---

## 🗣️ Supported Plans & Capabilities

The AI is trained to handle queries for the following HDFC policies:

| Plan | Best For |
|---|---|
| **HDFC Life Easy Health** | Family health coverage (floater) |
| **HDFC Life Cancer Care** | Critical illness / life cover |
| **HDFC Life Guaranteed Pension Plan** | Retirement savings (age 40–60) |
| **HDFC New Immediate Annuity Plan** | Immediate retirement income (age 60+) |

### What the AI Can Do

- ✅ Recommend a plan based on age, income, and family size
- ✅ Explain coverage, exclusions, waiting periods, and cancellation terms from policy documents
- ✅ File a new insurance claim (with or without document upload)
- ✅ Extract structured claim data from medical bills using Gemini Vision
- ✅ Detect potential claim fraud (exclusions, silly reasons, waiting period violations)
- ✅ Check renewal due dates and process one-click renewals
- ✅ Calculate premium estimates with GST breakdown
- ✅ Estimate annuity/pension payouts for retirement plans
- ✅ Generate post-call summaries and sync customer data

---

## 🔬 Running Tests

```bash
# Test voice API endpoints
python -m pytest tests/test_voice_api.py

# Test RAG retrieval
python tests/test_rag.py

# Test sentiment analysis
python tests/test_sentiment.py

# Simulate a full end-to-end chat session
python tests/simulate_chat.py

# Verify database integrity
python tests/verify_db.py
```

---

## 🧩 Key Technologies

| Technology | Purpose |
|---|---|
| **Google ADK** (`google-adk`) | Multi-agent framework for building and running agent pipelines |
| **Gemini 2.5 Flash** | Core LLM powering all agents |
| **Gemini Vision** | Extracts structured data from uploaded medical documents |
| **Gemini Embeddings** (`gemini-embedding-001`) | Generates vector embeddings for ChromaDB |
| **ChromaDB** | Persistent vector store for semantic policy document retrieval |
| **Flask** | Lightweight web server for Twilio voice webhooks |
| **Twilio** | Phone call integration (STT + TTS + webhook handling) |
| **Streamlit** | Browser-based chat dashboard |
| **SQLite** | Persistent customer, policy, and claims database |
| **Google Cloud TTS/STT** | Text-to-speech and speech-to-text for voice I/O |
| **python-dotenv** | Environment variable management |

---

## 📋 Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | Google AI Studio / Gemini API key |
| `GOOGLE_APPLICATION_CREDENTIALS` | ⚠️ Optional | Path to GCP service account JSON (for Cloud TTS/STT) |

---

## 🛡️ Fraud Detection Logic

The **Fraud Detector Sub-Agent** evaluates every claim against the following rules:

1. **Exclusion Check** — Rejects claims for cosmetic procedures, self-inflicted injuries, alcohol/drug abuse, congenital conditions
2. **Non-Medical Reason Check** — Rejects silly/invalid reasons (groceries, travel, weddings, etc.)
3. **Severe Reason Flag** — Flags surgeries, cancer, hospitalization for manual investigation
4. **Amount Threshold** — Flags mild illness claims > ₹50,000 for investigation
5. **Waiting Period** — Rejects claims filed within 30 days of policy commencement
6. **Prior Claim Status** — Flags profiles with previously rejected claims
7. **Sum Insured Cap** — Caps approval at the policy's total sum insured

---

## 👤 Customer Data Model

Each customer record stored in SQLite includes:

- `name`, `phone_number`, `age`, `income_bracket`, `family_size`
- `existing_policies` (JSON) — policy type, benefit, premium, commencement date
- `last_claim_date`, `last_claim_status`
- `renewal_due_date`
- `is_new_lead` flag

---

## 📄 License

This project is for educational and demonstration purposes. All HDFC plan data referenced is for illustrative use only.

---

*Built with ❤️ using Google ADK, Gemini 2.5 Flash, and Twilio.*
