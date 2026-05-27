# Finance Dashboard

A **local-first** personal finance dashboard. All data stays on your machine.
No cloud, no subscriptions, no ads.

```
Banks / Cards
     │
     ▼ Plaid (OAuth, read-only)
Backend (FastAPI + SQLite)
     │
     ▼ localhost:8000
Frontend (Next.js)
     │
     ▼ localhost:3000
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 20+ |
| Plaid account | Free sandbox at https://dashboard.plaid.com |

---

## Quick Start

### 1. Clone & configure

```bash
git clone <repo>
cd finance-dashboard
cp .env.example .env
```

Edit `.env`:

```
PLAID_CLIENT_ID=   # from Plaid dashboard
PLAID_SECRET=      # Sandbox secret
PLAID_ENV=sandbox
ENCRYPTION_KEY=    # generate below
```

Generate your encryption key (run once):

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output as `ENCRYPTION_KEY` in `.env`.

---

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run from the project root (important for relative imports)
cd ..
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: http://127.0.0.1:8000/docs

---

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

---

## Architecture

### Backend (`backend/`)

```
backend/
├── main.py              FastAPI app factory
├── config.py            Pydantic settings (reads .env)
├── db/
│   └── database.py      SQLAlchemy engine + session + Base
├── models/
│   └── models.py        ORM models (Institution, Account, Transaction, SyncState)
├── schemas/
│   └── schemas.py       Pydantic request/response schemas
├── plaid/
│   └── client.py        Plaid API client factory
├── services/
│   └── sync_service.py  Plaid sync orchestration
├── routes/
│   ├── plaid_routes.py
│   ├── transaction_routes.py
│   ├── account_routes.py
│   └── analytics_routes.py
└── utils/
    └── encryption.py    Fernet encrypt/decrypt helpers
```

### Key design decisions

**Cursor-based sync** — Plaid's `/transactions/sync` API is cursor-based.
Each sync call returns only what changed since the last cursor.  The cursor is
persisted in `SyncState` so the next sync is always incremental.

**Encrypted tokens** — Plaid access tokens are encrypted with Fernet (AES-128-CBC
+ HMAC-SHA256) before being written to SQLite.  The encryption key lives only in
`.env`, which is gitignored.

**localhost-only** — The backend binds to `127.0.0.1` and CORS is restricted to
`localhost:3000`.  The API is not reachable from the network.

**WAL mode** — SQLite is configured with `PRAGMA journal_mode=WAL` for better
concurrent read performance (UI reads while sync writes).

---

## API Reference

### Plaid

| Method | Path | Description |
|--------|------|-------------|
| POST | `/plaid/create_link_token` | Get a Plaid Link token |
| POST | `/plaid/exchange_public_token` | Exchange public token, link institution |
| POST | `/plaid/sync_transactions` | Sync transactions for an institution |

### Transactions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/transactions` | List with filters + pagination |
| GET | `/transactions/{id}` | Single transaction |

Query params: `start_date`, `end_date`, `category`, `account_id`, `merchant`,
`search`, `pending`, `page`, `page_size`, `sort_by`, `sort_dir`

### Accounts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/accounts` | All institutions + accounts |
| GET | `/accounts/{id}` | Single account |
| DELETE | `/accounts/institutions/{id}` | Unlink institution |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/analytics/spending_by_month` | Monthly totals |
| GET | `/analytics/category_breakdown` | Pie chart data |
| GET | `/analytics/top_merchants` | Top merchants by spend |
| GET | `/analytics/accounts_summary` | Per-account spend |

---

## Connecting a Bank

1. Open the app at http://localhost:3000
2. Go to **Accounts** → **Link Account**
3. The app fetches a link token from the backend
4. Plaid Link opens — use sandbox credentials:
   - Username: `user_good`
   - Password: `pass_good`
5. After connecting, the backend exchanges the public token and syncs transactions

---

## Security

- Bank credentials are **never** stored — only Plaid access tokens (encrypted)
- The backend is **localhost-only** (`127.0.0.1`)
- `.env` and `*.db` files are gitignored
- Plaid products are **read-only** (`transactions` only)
- All secrets come from environment variables

---

## Roadmap

- [ ] Frontend dashboard (Phase 2)
- [ ] Transaction table with filters (Phase 2)
- [ ] Recharts analytics (Phase 3)
- [ ] Docker Compose (Phase 4)
- [ ] Budget tracking (future)
- [ ] AI categorization (future)
- [ ] CSV import/export (future)
