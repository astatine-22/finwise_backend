from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
# NOTE: We removed 'import models' from here to prevent circular import errors

# Create SQLite database file
SQLALCHEMY_DATABASE_URL = "sqlite:///./finwise.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session in API routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- NEW HELPER FUNCTION ---
def get_or_create_google_user(db: Session, email: str, name: str):
    """
    Finds a user by email. If not found, creates a new one.
    Used for Google Sign-In where there is no password.
    """
    # --- IMPORT MODELS HERE INSTEAD ---
    # Moving the import inside the function solves the circular reference error,
    # because Base is fully defined by the time this function is called.
    import models
    # ----------------------------------

    # 1. Check if user already exists
    # We use .lower() to ensure emails are case-insensitive
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    
    if user:
        # User exists, just return them
        return user
    else:
        # 2. User doesn't exist, create a new account
        new_user = models.User(
            name=name,
            email=email.lower(),
            # We set password to an empty string as a placeholder. 
            # Standard login will fail because "" won't match any real password hash.
            password="", 
            xp=100 # Give starting XP
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user