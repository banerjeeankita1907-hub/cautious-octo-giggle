import pytest
from app import create_app, db, Product, User
from werkzeug.security import generate_password_hash


@pytest.fixture()
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "WTF_CSRF_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
    })
    with app.app_context():
        db.create_all()
        admin = User(name="Test Admin", email="admin@test.local",
                     password_hash=generate_password_hash("test-password-123"),
                     role="admin")
        db.session.add(admin)
        db.session.add(Product(sku="TEST-01", name="Test Product", category="Test",
                               unit_price=10, stock_qty=10, min_stock=2))
        db.session.commit()
    with app.test_client() as client:
        yield client
    with app.app_context():
        db.drop_all()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_dashboard_requires_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_admin_can_sign_in(client):
    response = client.post("/login", data={
        "email": "admin@test.local",
        "password": "test-password-123",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Good work starts with" in response.data


def test_failed_login_is_rejected(client):
    response = client.post("/login", data={
        "email": "admin@test.local",
        "password": "wrong-password",
    })
    assert response.status_code == 200
    assert b"incorrect" in response.data


def test_setup_wizard_only_works_without_users(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'setup.db'}",
        "WTF_CSRF_ENABLED": False,
    })
    with app.test_client() as client:
        response = client.post("/setup", data={
            "name": "First Admin",
            "email": "first@test.local",
            "password": "a-very-long-password",
            "confirm_password": "a-very-long-password",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Good work starts with" in response.data
