import csv
import io
import os
import secrets
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    database_url = os.getenv("DATABASE_URL", "sqlite:///stockpilot.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please sign in to continue."
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.template_filter("money")
    def money(value):
        return f"₹{float(value or 0):,.2f}"

    @app.context_processor
    def common_context():
        return {"brand": "StockPilot", "today": date.today()}

    def record(action, detail):
        db.session.add(AuditLog(actor_id=current_user.id if current_user.is_authenticated else None,
                                action=action, detail=detail[:240]))

    def roles_required(*roles):
        def decorator(fn):
            @wraps(fn)
            @login_required
            def wrapped(*args, **kwargs):
                if current_user.role not in roles:
                    abort(403)
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    def setup_needed():
        return User.query.count() == 0

    @app.before_request
    def first_run_redirect():
        endpoint = request.endpoint
        allowed = {"setup", "login", "static", "health"}
        if not setup_needed() or endpoint in allowed or endpoint is None:
            return None
        return redirect(url_for("setup"))

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
        return response

    @app.get("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok", "application": "StockPilot"}, 200

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if not setup_needed():
            return redirect(url_for("login"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            if not name or "@" not in email:
                flash("Enter a name and valid email address.", "error")
            elif len(password) < 10:
                flash("Use a password with at least 10 characters.", "error")
            elif password != confirm:
                flash("The passwords do not match.", "error")
            else:
                user = User(name=name, email=email, role="admin",
                            password_hash=generate_password_hash(password))
                db.session.add(user)
                db.session.commit()
                login_user(user)
                record("Account created", f"First administrator: {email}")
                db.session.commit()
                flash("Your workspace is ready. Welcome to StockPilot.", "success")
                return redirect(url_for("dashboard"))
        return render_template("page.html", page="setup", title="Create your workspace")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if setup_needed():
            return redirect(url_for("setup"))
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email, active=True).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user, remember=bool(request.form.get("remember")))
                return redirect(request.args.get("next") or url_for("dashboard"))
            flash("Email or password is incorrect.", "error")
        return render_template("page.html", page="login", title="Sign in")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been signed out.", "success")
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def dashboard():
        total_products = Product.query.count()
        inventory_value = db.session.query(func.coalesce(func.sum(Product.stock_qty * Product.unit_price), 0)).scalar()
        sales_today = db.session.query(func.coalesce(func.sum(Sale.total), 0)).filter(
            func.date(Sale.created_at) == date.today().isoformat()).scalar()
        sales_month = db.session.query(func.coalesce(func.sum(Sale.total), 0)).filter(
            Sale.created_at >= datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)).scalar()
        low_stock = Product.query.filter(Product.stock_qty <= Product.min_stock).order_by(Product.stock_qty.asc()).limit(8).all()
        recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(6).all()
        start = date.today() - timedelta(days=6)
        raw = db.session.query(func.date(Sale.created_at), func.sum(Sale.total)).filter(
            Sale.created_at >= datetime.combine(start, datetime.min.time())).group_by(func.date(Sale.created_at)).all()
        points = {str(day): float(total or 0) for day, total in raw}
        chart = [{"day": (start + timedelta(days=i)).strftime("%a"), "value": points.get((start + timedelta(days=i)).isoformat(), 0)}
                 for i in range(7)]
        return render_template("page.html", page="dashboard", title="Overview",
            total_products=total_products, inventory_value=inventory_value,
            sales_today=sales_today, sales_month=sales_month, low_stock=low_stock,
            recent_sales=recent_sales, chart=chart, max_chart=max([p["value"] for p in chart] + [1]))

    @app.route("/products", methods=["GET", "POST"])
    @roles_required("admin", "manager")
    def products():
        if request.method == "POST":
            sku = request.form.get("sku", "").strip().upper()
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip() or "General"
            try:
                price = float(request.form.get("unit_price", "0"))
                quantity = int(request.form.get("stock_qty", "0"))
                minimum = int(request.form.get("min_stock", "0"))
                if price < 0 or quantity < 0 or minimum < 0:
                    raise ValueError
            except ValueError:
                flash("Price, stock, and reorder level must be valid non-negative numbers.", "error")
                return redirect(url_for("products"))
            if not sku or not name:
                flash("SKU and product name are required.", "error")
            elif Product.query.filter_by(sku=sku).first():
                flash("That SKU already exists.", "error")
            else:
                item = Product(sku=sku, name=name, category=category, unit_price=price,
                               stock_qty=quantity, min_stock=minimum)
                db.session.add(item)
                record("Product created", f"{sku} · {name}")
                db.session.commit()
                flash("Product added to inventory.", "success")
            return redirect(url_for("products"))
        items = Product.query.order_by(Product.name.asc()).all()
        return render_template("page.html", page="products", title="Inventory", products=items)

    @app.post("/products/<int:product_id>/update")
    @roles_required("admin", "manager")
    def update_product(product_id):
        item = db.get_or_404(Product, product_id)
        try:
            item.unit_price = float(request.form.get("unit_price", item.unit_price))
            item.stock_qty = int(request.form.get("stock_qty", item.stock_qty))
            item.min_stock = int(request.form.get("min_stock", item.min_stock))
            if item.unit_price < 0 or min(item.stock_qty, item.min_stock) < 0:
                raise ValueError
        except ValueError:
            flash("Enter valid non-negative price and stock values.", "error")
            return redirect(url_for("products"))
        record("Product updated", f"{item.sku} · stock {item.stock_qty}")
        db.session.commit()
        flash("Inventory record updated.", "success")
        return redirect(url_for("products"))

    @app.route("/customers", methods=["GET", "POST"])
    @login_required
    def customers():
        if request.method == "POST":
            if current_user.role not in ("admin", "manager", "staff"):
                abort(403)
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower() or None
            phone = request.form.get("phone", "").strip() or None
            if not name:
                flash("Customer name is required.", "error")
            elif email and Customer.query.filter_by(email=email).first():
                flash("A customer with that email already exists.", "error")
            else:
                db.session.add(Customer(name=name, email=email, phone=phone))
                record("Customer created", name)
                db.session.commit()
                flash("Customer saved.", "success")
            return redirect(url_for("customers"))
        return render_template("page.html", page="customers", title="Customers",
                               customers=Customer.query.order_by(Customer.name.asc()).all())

    @app.get("/sales")
    @login_required
    def sales():
        records = Sale.query.order_by(Sale.created_at.desc()).limit(100).all()
        return render_template("page.html", page="sales", title="Sales", sales=records)

    @app.route("/sales/new", methods=["GET", "POST"])
    @login_required
    def new_sale():
        available = Product.query.filter(Product.stock_qty > 0).order_by(Product.name.asc()).all()
        customers_list = Customer.query.order_by(Customer.name.asc()).all()
        if request.method == "POST":
            product_ids = request.form.getlist("product_id")
            quantities = request.form.getlist("quantity")
            if len(product_ids) != len(quantities) or not product_ids:
                flash("Add at least one product to the sale.", "error")
                return redirect(url_for("new_sale"))
            line_map = {}
            try:
                for product_id, quantity in zip(product_ids, quantities):
                    pid, qty = int(product_id), int(quantity)
                    if qty < 1:
                        raise ValueError
                    line_map[pid] = line_map.get(pid, 0) + qty
                customer_id = request.form.get("customer_id") or None
                customer_id = int(customer_id) if customer_id else None
                if customer_id and not db.session.get(Customer, customer_id):
                    raise ValueError
            except (ValueError, TypeError):
                flash("Select valid products, quantities, and customer details.", "error")
                return redirect(url_for("new_sale"))
            try:
                lines = []
                total = 0.0
                for pid, qty in line_map.items():
                    item = db.session.get(Product, pid)
                    if not item or item.stock_qty < qty:
                        raise ValueError(f"Insufficient stock for product ID {pid}.")
                    lines.append((item, qty))
                    total += float(item.unit_price) * qty
                sale = Sale(invoice_no="SP-" + datetime.utcnow().strftime("%y%m%d%H%M%S") + secrets.token_hex(2).upper(),
                            customer_id=customer_id, user_id=current_user.id, total=total)
                db.session.add(sale)
                db.session.flush()
                for item, qty in lines:
                    item.stock_qty -= qty
                    db.session.add(SaleItem(sale_id=sale.id, product_id=item.id, quantity=qty,
                                            unit_price=item.unit_price))
                record("Sale recorded", f"{sale.invoice_no} · ₹{total:,.2f}")
                db.session.commit()
                flash(f"Sale {sale.invoice_no} recorded and inventory updated.", "success")
                return redirect(url_for("sale_detail", sale_id=sale.id))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "error")
            except Exception:
                db.session.rollback()
                app.logger.exception("Sale transaction failed")
                flash("The sale could not be saved. No stock was changed.", "error")
        return render_template("page.html", page="new_sale", title="New sale",
                               products=available, customers=customers_list)

    @app.get("/sales/<int:sale_id>")
    @login_required
    def sale_detail(sale_id):
        sale = db.get_or_404(Sale, sale_id)
        return render_template("page.html", page="sale_detail", title=sale.invoice_no, sale=sale)

    @app.get("/team")
    @roles_required("admin")
    def team():
        return render_template("page.html", page="team", title="Team",
                               users=User.query.order_by(User.created_at.desc()).all())

    @app.post("/team")
    @roles_required("admin")
    def add_team_member():
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "staff")
        password = request.form.get("password", "")
        if not name or "@" not in email or role not in ("manager", "staff") or len(password) < 10:
            flash("Enter valid details. Passwords must contain at least 10 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "error")
        else:
            db.session.add(User(name=name, email=email, role=role,
                                password_hash=generate_password_hash(password)))
            record("Team member added", f"{email} · {role}")
            db.session.commit()
            flash("Team member created.", "success")
        return redirect(url_for("team"))

    @app.post("/team/<int:user_id>/toggle")
    @roles_required("admin")
    def toggle_user(user_id):
        member = db.get_or_404(User, user_id)
        if member.id == current_user.id:
            flash("You cannot deactivate your own account.", "error")
        else:
            member.active = not member.active
            record("Team access changed", f"{member.email} · {'active' if member.active else 'inactive'}")
            db.session.commit()
            flash("Team access updated.", "success")
        return redirect(url_for("team"))

    @app.get("/audit")
    @roles_required("admin", "manager")
    def audit():
        events = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(150).all()
        return render_template("page.html", page="audit", title="Activity log", events=events)

    @app.get("/reports/sales.csv")
    @roles_required("admin", "manager")
    def sales_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Invoice", "Date (UTC)", "Customer", "Staff", "Total INR"])
        for sale in Sale.query.order_by(Sale.created_at.desc()).all():
            writer.writerow([sale.invoice_no, sale.created_at.isoformat(),
                sale.customer.name if sale.customer else "Walk-in",
                sale.user.name if sale.user else "—", f"{sale.total:.2f}"])
        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = "attachment; filename=stockpilot-sales.csv"
        return response

    with app.app_context():
        db.create_all()
        if os.getenv("SEED_DEMO_DATA", "false").lower() == "true" and Product.query.count() == 0:
            demo = [
                ("ELEC-001", "Wireless Mouse", "Electronics", 799, 34, 8),
                ("ELEC-002", "Mechanical Keyboard", "Electronics", 2499, 12, 4),
                ("HOME-001", "Insulated Bottle", "Home", 499, 7, 10),
                ("OFF-001", "A5 Notebook", "Stationery", 99, 120, 20),
                ("OFF-002", "Gel Pen Set", "Stationery", 149, 55, 12),
            ]
            db.session.add_all([Product(sku=s, name=n, category=c, unit_price=p, stock_qty=q, min_stock=m)
                                for s, n, c, p, q, m in demo])
            db.session.add_all([Customer(name="Walk-in Business", email="buyer@example.com"),
                                Customer(name="Northstar Traders", email="orders@northstar.example")])
            db.session.commit()

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("page.html", page="error", title="Access denied",
                               code=403, message="Your account does not have permission to open this page."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("page.html", page="error", title="Not found",
                               code=404, message="The requested record or page could not be found."), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template("page.html", page="error", title="Server error",
                               code=500, message="Something went wrong. Please try again."), 500

    return app


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="General")
    unit_price = db.Column(db.Float, nullable=False, default=0)
    stock_qty = db.Column(db.Integer, nullable=False, default=0)
    min_stock = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    customer = db.relationship("Customer")
    user = db.relationship("User")
    items = db.relationship("SaleItem", backref="sale", cascade="all, delete-orphan")


class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    product = db.relationship("Product")


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    detail = db.Column(db.String(240), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    actor = db.relationship("User")


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
