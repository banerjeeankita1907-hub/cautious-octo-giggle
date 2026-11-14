# Industry Project Report — StockPilot

## 1. Project overview

**Title:** StockPilot — Inventory & Sales Management System  
**Category:** Full-stack web application / Retail operations  
**Problem addressed:** Small businesses commonly maintain product availability, customer contacts and sales records in separate spreadsheets or manual registers. This creates stock mismatches, repetitive entry and weak visibility into business performance.

StockPilot provides a single role-aware web workspace for product records, customer information, sales invoices and operational reporting. Completing a sale validates stock and updates inventory as one database transaction.

## 2. Objectives

1. Maintain a searchable, SKU-based product catalogue.
2. Track current stock and minimum reorder quantities.
3. Record multi-product sales and associate them with customers.
4. Prevent a sale from completing when requested quantities exceed stock.
5. Provide role-based access for administrators, managers and staff.
6. Expose revenue and inventory indicators on a dashboard.
7. Maintain an audit trail and export sales to CSV.
8. Support local development and cloud deployment.

## 3. Functional modules

| Module | Responsibilities |
|---|---|
| Authentication | First-run admin creation, login/logout, password hashing |
| Dashboard | Inventory count/value, daily/monthly sales, recent invoices, low-stock list |
| Inventory | Create products, maintain SKU, category, unit price, quantity and reorder threshold |
| Customers | Store company/person names and contact details |
| Sales | Multi-line invoice, customer selection, quantity validation and inventory deduction |
| Team | Admin-managed accounts and admin/manager/staff permissions |
| Audit | Timestamped history of operational actions |
| Reports | CSV sales register |
| Health | Database-backed /health endpoint |

## 4. Technology stack

- **Backend:** Python 3.12 and Flask.
- **ORM/database:** Flask-SQLAlchemy; SQLite for local development and PostgreSQL for hosted deployment.
- **Authentication:** Flask-Login and Werkzeug password hashing.
- **Request security:** Flask-WTF CSRF protection, secure cookie configuration and response security headers.
- **Frontend:** HTML, CSS and vanilla JavaScript with responsive layouts.
- **Production server:** Gunicorn.
- **Containerization/deployment:** Docker and Render Blueprint.

## 5. Data model

- **User:** name, unique email, password hash, role, active status and creation time.
- **Product:** unique SKU, name, category, unit price, stock quantity and reorder level.
- **Customer:** name, optional unique email and phone.
- **Sale:** invoice identifier, optional customer, creator, total and timestamp.
- **SaleItem:** sale, product, quantity and captured unit price.
- **AuditLog:** actor, event name, detail and timestamp.

Relationship overview:

```
User 1 ─── * Sale 1 ─── * SaleItem * ─── 1 Product
  │
  └────── * AuditLog

Customer 1 ─── * Sale
```

## 6. Key business logic

A sale request may contain multiple product lines. Duplicate product lines are aggregated before stock checks. Every requested product is checked against its available quantity. The invoice and line items are written and stock is decremented in the same SQLAlchemy transaction. If validation or persistence fails, the transaction is rolled back so a partially completed sale is not committed.

Inventory alerts are raised when:

```
stock_qty <= min_stock
```

Sales revenue is calculated from the stored unit price multiplied by quantity. Amounts are displayed in Indian rupees (INR). The application does not calculate GST, tax, discounts or payment settlement.

## 7. Access-control matrix

| Capability | Admin | Manager | Staff |
|---|:---:|:---:|:---:|
| View dashboard | ✓ | ✓ | ✓ |
| View inventory | ✓ | ✓ | — |
| Create/update inventory | ✓ | ✓ | — |
| View/add customers | ✓ | ✓ | ✓ |
| Create/view sales | ✓ | ✓ | ✓ |
| Export sales CSV | ✓ | ✓ | — |
| View activity log | ✓ | ✓ | — |
| Create/deactivate team users | ✓ | — | — |

## 8. Security and reliability

Passwords are stored as salted hashes, not plaintext. CSRF tokens protect form submissions. Role decorators guard management and reporting routes. Session cookies are HTTP-only and SameSite=Lax; the Render configuration enables Secure cookies. Responses include basic content-sniffing, framing and referrer protections. Sale processing validates inventory before commit and explicitly rolls back on errors. A health endpoint checks database connectivity.

## 9. Validation and testing

The pytest suite covers the health endpoint, unauthenticated dashboard redirect, successful administrator sign-in, rejected incorrect credentials and first-run workspace setup. Execute with:

```bash
pytest -q
```

The app also includes a live /health endpoint for hosting-provider checks. A production launch should additionally include a successful hosted smoke test and a backup/restore exercise.

## 10. Deployment

The repository includes a Render Blueprint. It defines a Flask web service, a PostgreSQL database, generated SECRET_KEY, secure cookies and sample catalogue/customer data. Apply the Blueprint from Render to create the public service URL, then use the first-run wizard to create an administrator.

The committed free-tier Blueprint is intended for evaluation. Render's free Postgres database expires after 30 days and free web instances may spin down; upgrade the database and web service before relying on the application for ongoing business operations.

## 11. Limitations and future scope

- GST/tax invoices, payment gateway integration, returns/refunds and purchase-order workflows are not implemented.
- Inventory updates are simple counts; multi-warehouse transfers and serial/batch tracking are outside scope.
- Sales are represented as completed transactions; there is no external payment processor.
- Add database migrations, structured observability, rate limiting, automated backups and end-to-end browser tests before larger production rollouts.

## 12. Conclusion

StockPilot demonstrates an integrated retail workflow from product registration through customer-linked sale recording and stock reconciliation. The architecture separates persistence, application routing and browser presentation, supports both SQLite and PostgreSQL, and can be run locally or deployed as a container-backed web service.
