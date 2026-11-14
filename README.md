# StockPilot — Inventory & Sales Management

StockPilot is a full-stack business operations application for small and mid-sized retailers. It brings inventory, customer records, point-of-sale transactions, team access and operational reporting into one responsive workspace.

https://stockpilot-trjk.onrender.com
## Features

- **Overview dashboard:** inventory valuation, daily and month-to-date sales, seven-day sales activity, reorder attention and recent invoices.
- **Inventory control:** SKU-based product catalogue, category, price, on-hand units and minimum/reorder quantity; stock automatically decreases after successful sales.
- **Point of sale:** customer-linked or walk-in invoices, multiple product lines, quantity validation and transactional stock deduction.
- **Customer directory:** customer/company names, email and phone.
- **Team access:** administrator, manager and staff roles; administrator can create/deactivate team access.
- **Operational audit log:** records important actions with actor and timestamp.
- **CSV reporting:** export the sales register for spreadsheet analysis.
- **Security:** password hashing, CSRF protection, secure session-cookie settings, role checks, response security headers and a database health endpoint.
- **Responsive interface:** desktop and mobile layouts.

## Local setup

Requires Python 3.12+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

Set a secret key before launching:

```bash
# macOS/Linux
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
# Windows PowerShell
# $env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python app.py
```

Open http://127.0.0.1:5000. The first-run setup wizard creates the first administrator. There are no hard-coded production credentials.

## Docker

```bash
docker build -t stockpilot .
docker run --rm -p 5000:5000 -e SECRET_KEY="replace-with-a-long-random-secret" stockpilot
```

For a persistent production deployment, point `DATABASE_URL` to PostgreSQL. SQLite is provided as the local-development default.

## Demo data

The Render Blueprint enables sample catalogue/customer records through `SEED_DEMO_DATA=true`. For local demo data, set the same environment variable before starting the app. The seed does not create a default user; create the first administrator through the setup page.

## Tests

```bash
pytest -q
```

## Technology stack

Python 3.12 · Flask · Flask-Login · Flask-SQLAlchemy · SQLAlchemy · PostgreSQL/SQLite · Flask-WTF · Gunicorn · HTML5 · CSS3 · JavaScript · Docker · Render Blueprint.

## Project structure

```
.
├── app.py
├── requirements.txt
├── Dockerfile
├── render.yaml
├── templates/
│   └── page.html
├── static/
│   ├── app.css
│   └── app.js
└── tests/
    └── test_app.py
```

## Production hardening checklist

Before storing real customer or financial data: upgrade the free database to a persistent paid database tier; configure automated backups and a retention policy; use a unique secret key; restrict administrator access; confirm privacy/legal requirements for your jurisdiction; and run the included tests plus a deployment smoke test. Currency display is INR and stored sales amounts are not a tax or GST calculation.
