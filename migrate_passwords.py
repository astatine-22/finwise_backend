"""
Password Migration Script for FinWise
======================================
This script migrates existing plaintext passwords to bcrypt hashes.

Run this script ONCE after upgrading to the new security system.

Usage:
    cd finWise_backend
    python migrate_passwords.py

IMPORTANT: 
- Back up your database before running this script!
- This script is idempotent - it won't rehash already hashed passwords.
"""

from database import SessionLocal, engine
import models
from passlib.context import CryptContext

# Initialize bcrypt context (same as in main.py)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def is_bcrypt_hash(password: str) -> bool:
    """
    Check if a password is already a bcrypt hash.
    Bcrypt hashes start with '$2a$', '$2b$', or '$2y$' and are 60 characters long.
    """
    if not password:
        return False
    return (
        len(password) == 60 and 
        (password.startswith('$2a$') or password.startswith('$2b$') or password.startswith('$2y$'))
    )


def migrate_passwords():
    """Migrate all plaintext passwords to bcrypt hashes."""
    
    print("=" * 60)
    print("FinWise Password Migration Script")
    print("=" * 60)
    print()
    
    db = SessionLocal()
    
    try:
        # Get all users
        users = db.query(models.User).all()
        total_users = len(users)
        
        print(f"Found {total_users} users in database.\n")
        
        migrated_count = 0
        skipped_google = 0
        skipped_already_hashed = 0
        
        for user in users:
            # Skip users with empty passwords (Google sign-in users)
            if not user.password or user.password == "":
                print(f"  [SKIP] {user.email} - Google sign-in user (no password)")
                skipped_google += 1
                continue
            
            # Skip already hashed passwords
            if is_bcrypt_hash(user.password):
                print(f"  [SKIP] {user.email} - Password already hashed")
                skipped_already_hashed += 1
                continue
            
            # Hash the plaintext password
            old_password = user.password
            hashed_password = pwd_context.hash(old_password)
            user.password = hashed_password
            
            print(f"  [MIGRATED] {user.email} - Password hashed successfully")
            migrated_count += 1
        
        # Commit all changes
        db.commit()
        
        print()
        print("=" * 60)
        print("Migration Summary")
        print("=" * 60)
        print(f"  Total users:           {total_users}")
        print(f"  Passwords migrated:    {migrated_count}")
        print(f"  Skipped (Google):      {skipped_google}")
        print(f"  Skipped (already hash):{skipped_already_hashed}")
        print()
        
        if migrated_count > 0:
            print("✅ Migration completed successfully!")
            print("   Users can now login with their existing passwords.")
        else:
            print("ℹ️  No passwords needed migration.")
        
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_passwords()
