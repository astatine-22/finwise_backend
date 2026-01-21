import sqlite3
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models
from passlib.context import CryptContext

# Use a separate test database
TEST_DB_URL = "sqlite:///./test_finwise.db"
if os.path.exists("test_finwise.db"):
    os.remove("test_finwise.db")

# Setup test database engine and session
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Create tables in test DB
models.Base.metadata.create_all(bind=test_engine)

pwd_context = CryptContext(schemes=["bcrypt", "plaintext"], deprecated=["plaintext"])

def test_migration_on_login():
    db = TestSessionLocal()

    email = "legacy_user@example.com"
    password = "legacy_password_123"

    # 1. Create a user with PLAIN TEXT password manually in TEST DB
    conn = sqlite3.connect("test_finwise.db")
    cursor = conn.cursor()
    # Need to include budget_limit as it is NOT NULL
    cursor.execute(
        "INSERT INTO users (name, email, password, xp, budget_limit) VALUES (?, ?, ?, ?, ?)",
        ("Legacy User", email, password, 100, 20000.0)
    )
    conn.commit()
    conn.close()

    # 2. Simulate Login Logic
    db_user = db.query(models.User).filter(models.User.email == email).first()
    assert db_user.password == password # Should be plain text

    # Verify password (should work with plaintext scheme)
    assert pwd_context.verify(password, db_user.password)

    # Check if needs update
    if pwd_context.needs_update(db_user.password):
        print("Password needs update (Correct)")
        new_hash = pwd_context.hash(password)
        db_user.password = new_hash
        db.commit()
    else:
        print("Password DOES NOT need update (Fail)")
        assert False

    # 3. Verify it is now hashed
    db.refresh(db_user)
    assert db_user.password != password
    assert db_user.password.startswith("$2b$") or db_user.password.startswith("$2a$")
    assert pwd_context.verify(password, db_user.password)

    print("✅ Migration on login verified.")
    db.close()

if __name__ == "__main__":
    test_migration_on_login()
    # Cleanup
    if os.path.exists("test_finwise.db"):
        os.remove("test_finwise.db")
