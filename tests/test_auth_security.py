import sqlite3
import os
import pytest
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def test_password_hashing():
    db = TestSessionLocal()

    email = "test_secure@example.com"
    password = "secure_password_123"

    hashed_password = pwd_context.hash(password)

    new_user = models.User(
        name="Test User",
        email=email,
        password=hashed_password,
        xp=100
    )
    db.add(new_user)
    db.commit()

    # Verify it's NOT stored as plain text using raw SQL on the TEST DB
    connection = sqlite3.connect("test_finwise.db")
    cursor = connection.cursor()
    cursor.execute("SELECT password FROM users WHERE email = ?", (email,))
    stored_password = cursor.fetchone()[0]
    connection.close()

    assert stored_password != password
    assert pwd_context.verify(password, stored_password)

    db.close()

if __name__ == "__main__":
    test_password_hashing()
    print("✅ Test Passed: Password is hashed and verifiable.")
    # Cleanup
    if os.path.exists("test_finwise.db"):
        os.remove("test_finwise.db")
