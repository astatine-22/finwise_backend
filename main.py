from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
import yfinance as yf
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import requests

# --- SECURITY IMPORTS ---
from jose import JWTError, jwt
import secrets
from passlib.context import CryptContext

# --- IMPORTS FOR GOOGLE LOGIN ---
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import database
# ------------------------------------

import models
from database import engine, get_db

# Create database tables automatically
models.Base.metadata.create_all(bind=engine)

app = FastAPI()


# =============================================================================
# SAFE DATABASE MIGRATION (runs on startup)
# =============================================================================

def perform_safe_migration():
    """
    Perform safe database migrations without data loss.
    Adds missing columns if they don't exist.
    """
    migration_queries = [
        # Add hashed_password column if it doesn't exist (for legacy compatibility)
        # Note: Our model uses 'password' which already stores hashed values
        # This is here in case any old schema has issues
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'password'
            ) THEN
                ALTER TABLE users ADD COLUMN password VARCHAR;
            END IF;
        END $$;
        """,
    ]
    
    try:
        with engine.connect() as conn:
            for query in migration_queries:
                conn.execute(text(query))
            conn.commit()
        print("✅ Safe database migration completed successfully.")
    except Exception as e:
        print(f"⚠️ Migration warning (may be non-critical): {e}")


@app.on_event("startup")
async def startup_event():
    """Run safe migrations when the server starts."""
    print("🚀 Starting FinWise API server...")
    perform_safe_migration()
    print("✅ Server startup complete.")

# =============================================================================
# CORS CONFIGURATION - Cloud Ready
# =============================================================================
# Read allowed origins from environment variable, or allow all for mobile app access
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
if cors_origins_env == "*":
    allow_origins = ["*"]
else:
    # Split comma-separated origins
    allow_origins = [origin.strip() for origin in cors_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

# JWT Configuration
# Read from environment variable in production, fallback to default for local dev
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production-finwise-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing
# We support "plaintext" for backward compatibility with existing users
pwd_context = CryptContext(schemes=["bcrypt", "plaintext"], deprecated=["plaintext"])

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# --- GOOGLE OAUTH CONFIGURATION ---
# Read from environment variable in production
GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID", 
    "783108831764-djrpp609l2rj7kch5imn32d5rb474qf7.apps.googleusercontent.com"
)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """
    Dependency that validates JWT token and returns the current user.
    Use this to protect any authenticated endpoints.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if user is None:
        raise credentials_exception
    return user


# =============================================================================
# GAMIFICATION HELPER FUNCTIONS
# =============================================================================

# Level definitions: (min_xp, level_number, title)
LEVEL_THRESHOLDS = [
    (0, 1, "Novice"),
    (500, 2, "Rookie"),
    (1500, 3, "Pro"),
    (3000, 4, "Expert"),
    (5000, 5, "Master"),
]


def calculate_level(xp: int) -> dict:
    """
    Calculate user's level based on XP.
    Returns dict with level info and progress to next level.
    """
    current_level = 1
    current_title = "Novice"
    current_min_xp = 0
    next_level_xp = 500
    
    for i, (min_xp, level, title) in enumerate(LEVEL_THRESHOLDS):
        if xp >= min_xp:
            current_level = level
            current_title = title
            current_min_xp = min_xp
            # Get XP needed for next level
            if i + 1 < len(LEVEL_THRESHOLDS):
                next_level_xp = LEVEL_THRESHOLDS[i + 1][0]
            else:
                next_level_xp = min_xp + 2000  # Max level, show some progress
    
    # Calculate progress percentage
    xp_in_current_level = xp - current_min_xp
    xp_range = next_level_xp - current_min_xp
    progress = min(1.0, xp_in_current_level / xp_range) if xp_range > 0 else 1.0
    
    return {
        "level": current_level,
        "title": current_title,
        "xp_for_next_level": next_level_xp,
        "progress_to_next": round(progress, 2)
    }


def update_user_streak(user: models.User, db: Session) -> int:
    """
    Update user's streak based on activity.
    Call this on key actions (add expense, trade, etc.)
    Returns the updated streak count.
    """
    from datetime import date
    today = date.today()
    
    if user.last_activity_date is None:
        # First activity ever
        user.current_streak = 1
    elif user.last_activity_date == today:
        # Already active today, no change
        pass
    elif user.last_activity_date == today - timedelta(days=1):
        # Consecutive day - increment streak
        user.current_streak = (user.current_streak or 0) + 1
    else:
        # Streak broken - reset to 1
        user.current_streak = 1
    
    user.last_activity_date = today
    db.commit()
    
    return user.current_streak


def check_and_award_achievement(user: models.User, achievement_key: str, db: Session) -> bool:
    """
    Check if user has achievement and award it if not.
    Returns True if newly awarded, False if already had it.
    """
    # Check if achievement exists
    achievement = db.query(models.Achievement).filter(
        models.Achievement.key == achievement_key
    ).first()
    
    if not achievement:
        return False
    
    # Check if user already has this achievement
    existing = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == user.id,
        models.UserAchievement.achievement_id == achievement.id
    ).first()
    
    if existing:
        return False
    
    # Award the achievement
    new_achievement = models.UserAchievement(
        user_id=user.id,
        achievement_id=achievement.id,
        earned_at=datetime.utcnow()
    )
    db.add(new_achievement)
    
    # Add XP reward
    user.xp = (user.xp or 0) + achievement.xp_reward
    
    db.commit()
    return True


# --- Pydantic Models (Data Shapes) ---

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleLoginRequest(BaseModel):
    token: str

class UserProfile(BaseModel):
    name: str
    xp: int
    profile_picture: Optional[str] = None

class AuthResponse(BaseModel):
    message: str
    user_id: Optional[int] = None
    user: Optional[UserProfile] = None

# UPDATED: Added optional 'date' field.
# Pydantic automatically parses ISO 8601 strings into datetime objects.
class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str
    email: str
    date: Optional[datetime] = None 

class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: float
    category: str
    date: str
    
    class Config:
        orm_mode = True

class BudgetSummaryResponse(BaseModel):
    total_spent: float
    limit: float
    remaining: float

class CategorySummary(BaseModel):
    category: str
    total_amount: float

class SimpleResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    """Response model for JWT token authentication."""
    access_token: str
    token_type: str = "bearer"
    user_id: Optional[int] = None
    name: Optional[str] = None
    user: Optional[UserProfile] = None  # Keep for backward compatibility with Google login


class ProfilePictureUpdate(BaseModel):
    email: str
    profile_picture: str  # Base64 encoded image


class ProfileUpdate(BaseModel):
    email: str
    name: Optional[str] = None
    profile_picture: Optional[str] = None


# --- HELPER FUNCTION: Date Range Calculator ---
def get_start_date_for_range(range_str: str) -> Optional[datetime]:
    # Use utcnow to ensure consistent server time
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    if range_str == "today":
        return today
    elif range_str == "7d":
        return today - timedelta(days=7)
    elif range_str == "1m":
        # Simple approximation: 30 days
        return today - timedelta(days=30)
    elif range_str == "6m":
        # Simple approximation: 180 days
        return today - timedelta(days=180)
    elif range_str == "1y":
        return today - timedelta(days=365)
    elif range_str == "all":
        return None # No start date limit
    else:
        # Default to 1 month if unrecognized
        return today - timedelta(days=30)
# --------------------------------------------------


# --- API ROUTES ---

# ROOT HEALTH CHECK
@app.get("/")
def health_check():
    """Root endpoint to verify the server is running."""
    return {"status": "ok", "message": "FinWise Backend is running!"}

# 1. SIGNUP
@app.post("/api/auth/signup", response_model=SimpleResponse)
def signup(user: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if user with this email already exists
    db_user = db.query(models.User).filter(models.User.email == user.email.lower()).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email ID already exists")

    hashed_password = pwd_context.hash(user.password)
    new_user = models.User(
        name=user.name,
        email=user.email.lower(),
        password=hashed_password,
        xp=100
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created successfully"}

# 2. NORMAL LOGIN (with password verification)
@app.post("/api/auth/login", response_model=TokenResponse)
def login(user: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT."""
    db_user = db.query(models.User).filter(models.User.email == user.email.lower()).first()
    
    # Check if user exists
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    # Check if this is a Google-only account (empty password)
    if not db_user.password:
        raise HTTPException(status_code=400, detail="Please login with Google")
    
    # Verify password
    if not pwd_context.verify(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    # Check if password needs an update (e.g. if it was plaintext)
    if pwd_context.needs_update(db_user.password):
        db_user.password = pwd_context.hash(user.password)
        db.commit()

    # Create and return JWT token
    access_token = create_access_token(data={"sub": db_user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user.id,
        "name": db_user.name
    }

# 3. GOOGLE LOGIN (with JWT token)
@app.post("/api/auth/google", response_model=TokenResponse)
def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    """Authenticate via Google OAuth and return JWT."""
    try:
        idinfo = id_token.verify_oauth2_token(
            request.token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        email = idinfo['email']
        name = idinfo.get('name', 'Google User') 

        user = database.get_or_create_google_user(db, email, name)

        # Create and return JWT token
        access_token = create_access_token(data={"sub": user.email})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {"name": user.name, "xp": user.xp, "profile_picture": user.profile_picture}
        }

    except ValueError as e:
        print(f"Google token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google token")

# 4. GET USER DETAILS
@app.get("/api/user/{email}", response_model=UserProfile)
def get_user_details(email: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"name": user.name, "xp": user.xp, "profile_picture": user.profile_picture}


# 5. UPDATE PROFILE PICTURE
@app.put("/api/user/profile-picture", response_model=SimpleResponse)
def update_profile_picture(request: ProfilePictureUpdate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.profile_picture = request.profile_picture
    db.commit()
    
    return {"message": "Profile picture updated successfully"}


# 6. UPDATE USER PROFILE (name and profile picture)
@app.put("/api/user/profile", response_model=SimpleResponse)
def update_user_profile(request: ProfileUpdate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.name is not None:
        user.name = request.name
    if request.profile_picture is not None:
        user.profile_picture = request.profile_picture
    
    db.commit()
    
    return {"message": "Profile updated successfully"}


# 6b. UPDATE BUDGET LIMIT
class BudgetLimitUpdate(BaseModel):
    email: str
    budget_limit: float = Field(..., gt=0, description="Monthly budget limit in ₹")


@app.put("/api/user/budget-limit", response_model=SimpleResponse)
def update_budget_limit(request: BudgetLimitUpdate, db: Session = Depends(get_db)):
    """
    Update the user's monthly budget limit.
    """
    user = db.query(models.User).filter(models.User.email == request.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.budget_limit = request.budget_limit
    db.commit()
    
    return {"message": f"Budget limit updated to ₹{request.budget_limit:,.2f}"}


# --- BUDGET & EXPENSE ROUTES ---

# 5. ADD EXPENSE (UPDATED to accept optional date - with gamification)
@app.post("/api/expenses", response_model=SimpleResponse)
def add_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == expense.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Determine the date: use provided date if available, otherwise use current UTC time
    expense_date = expense.date if expense.date else datetime.utcnow()

    new_expense = models.Expense(
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        user_id=user.id,
        date=expense_date
    )
    
    db.add(new_expense)
    db.commit()
    
    # --- GAMIFICATION: Update streak and check achievements ---
    update_user_streak(user, db)
    
    # Check for first expense achievement
    expense_count = db.query(models.Expense).filter(models.Expense.user_id == user.id).count()
    if expense_count == 1:
        check_and_award_achievement(user, "first_expense", db)
    
    # Check for streak achievements
    if user.current_streak >= 7:
        check_and_award_achievement(user, "week_streak", db)
    if user.current_streak >= 30:
        check_and_award_achievement(user, "month_streak", db)
    # ---------------------------------------------------------
    
    return {"message": "Expense added!"}

# 6. GET EXPENSES LIST (With Range Filter)
@app.get("/api/expenses/{email}", response_model=List[ExpenseResponse])
def get_expenses(email: str, range: str = Query("1m"), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        return []
        
    query = db.query(models.Expense).filter(models.Expense.user_id == user.id)

    start_date = get_start_date_for_range(range)
    if start_date:
        query = query.filter(models.Expense.date >= start_date)

    # Order by newest first
    expenses = query.order_by(models.Expense.date.desc()).all()
    
    results = []
    for exp in expenses:
        display_date = exp.date if exp.date else datetime.utcnow()
        results.append({
            "id": exp.id,
            "title": exp.title,
            "amount": exp.amount,
            "category": exp.category,
            # Format date for display on frontend
            "date": display_date.strftime("%b %d, %Y") 
        })
    return results

# 7. GET BUDGET SUMMARY (With Range Filter - uses user's configurable budget limit)
@app.get("/api/budget/summary/{email}", response_model=BudgetSummaryResponse)
def get_budget_summary(email: str, range: str = Query("1m"), db: Session = Depends(get_db)):
    """
    Fetches budget summary using the user's configured budget limit.
    Falls back to default ₹20,000 if user not found or limit not set.
    """
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    
    # Get user's budget limit (or default if not set/user not found)
    budget_limit = user.budget_limit if user and user.budget_limit else 20000.0
    
    if not user:
        return {"total_spent": 0, "limit": budget_limit, "remaining": budget_limit}

    query = db.query(models.Expense).filter(models.Expense.user_id == user.id)
    
    start_date = get_start_date_for_range(range)
    if start_date:
        query = query.filter(models.Expense.date >= start_date)

    expenses = query.all()
    total_spent = sum(e.amount for e in expenses)
    
    return {
        "total_spent": total_spent,
        "limit": budget_limit,
        "remaining": budget_limit - total_spent
    }

# 8. GET SPENDING BY CATEGORY (Pie Chart Data - With Range Filter)
@app.get("/api/budget/categories/{email}", response_model=List[CategorySummary])
def get_spending_by_category(email: str, range: str = Query("1m"), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        return []

    start_date = get_start_date_for_range(range)

    # Build query: group by category and sum amounts
    query = db.query(
        models.Expense.category,
        func.sum(models.Expense.amount).label("total_amount")
    ).filter(
        models.Expense.user_id == user.id
    )

    if start_date:
        query = query.filter(models.Expense.date >= start_date)

    category_totals = query.group_by(models.Expense.category).all()

    results = []
    for cat, total in category_totals:
        safe_total = total if total is not None else 0.0
        results.append({"category": cat, "total_amount": safe_total})
    
    return results

    # --- NEW DELETE ENDPOINT ---

@app.delete("/api/expenses/{expense_id}", response_model=SimpleResponse)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    # 1. Find the expense by ID
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    
    # 2. If not found, return a 404 error
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # 3. Delete it and save changes
    db.delete(expense)
    db.commit()
    
    return {"message": "Expense deleted successfully"}

# ---------------------------

# =============================================================================
# DEBUG/MAINTENANCE ENDPOINTS
# =============================================================================

@app.delete("/api/debug/cleanup-duplicates", response_model=SimpleResponse)
def cleanup_duplicate_expenses(
    email: str = Query(..., description="User email to clean up duplicates for"),
    ignore_date: bool = Query(False, description="If True, ignores date and only checks title, amount, category"),
    db: Session = Depends(get_db)
):
    """
    
    Duplicates are identified by matching:
    - title (exact match)
    - amount (exact match)
    - category (exact match)
    - date (within 60 seconds tolerance to catch double-clicks)
    
    Keeps the first occurrence (lowest ID) and deletes all subsequent duplicates.
    """
    # Find the user
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Fetch all expenses for this user, ordered by ID ascending
    expenses = db.query(models.Expense).filter(
        models.Expense.user_id == user.id
    ).order_by(models.Expense.id.asc()).all()
    
    original_count = len(expenses)
    
    if original_count == 0:
        return {"message": "No expenses found for this user."}
    
    # Track which expenses we've seen and which are duplicates
    seen = {}  # signature -> first expense object
    duplicates_to_delete = []
    
    for expense in expenses:
        if ignore_date:
            # Ignore date completely - only check title, amount, category
            signature = (
                expense.title.strip().lower(),
                float(expense.amount),
                expense.category.strip().lower()
            )
        else:
            # Create a signature with timestamp rounded to 60-second buckets
            # This catches double-clicks and rapid duplicate submissions
            expense_timestamp = expense.date.timestamp() if expense.date else 0
            time_bucket = int(expense_timestamp // 60)  # 60-second buckets
            
            signature = (
                expense.title.strip().lower(),
                float(expense.amount),
                expense.category.strip().lower(),
                time_bucket  # Time rounded to nearest minute
            )
        
        if signature in seen:
            # This is a duplicate - mark it for deletion
            duplicates_to_delete.append(expense)
        else:
            # First time seeing this signature - keep it
            seen[signature] = expense
    
    # Delete all duplicates
    deleted_count = 0
    for duplicate in duplicates_to_delete:
        db.delete(duplicate)
        deleted_count += 1
    
    db.commit()
    
    remaining_count = original_count - deleted_count
    
    return {
        "message": f"Found {original_count} expenses. Removed {deleted_count} duplicates. {remaining_count} expenses remaining."
    }

@app.delete("/api/debug/delete-all-expenses", response_model=SimpleResponse)
def delete_all_expenses_for_user(
    email: str = Query(..., description="User email to delete all expenses for"),
    db: Session = Depends(get_db)
):
    ""\"
    DEBUG endpoint to delete ALL expenses for a specific user.
    Use this to clear test data or start fresh.
    ""\"
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get count before deletion
    expense_count = db.query(models.Expense).filter(models.Expense.user_id == user.id).count()
    
    # Delete all expenses for this user
    db.query(models.Expense).filter(models.Expense.user_id == user.id).delete()
    db.commit()
    
    return {"message": f"Deleted {expense_count} expenses for {email}. Database is now clean."}

# ---------------------------


# ============================================================================
# LEARN MODULE - Educational Video Content
# ============================================================================

# --- Learn Module Pydantic Schemas ---

class LearnVideoResponse(BaseModel):
    """Response schema for a single educational video."""
    id: int
    title: str
    description: Optional[str]
    thumbnail_url: Optional[str]
    youtube_video_id: str
    category: str
    duration_minutes: Optional[int]
    is_featured: bool

    class Config:
        orm_mode = True


class LessonCompleteRequest(BaseModel):
    """Request model for completing a lesson and earning XP."""
    email: str
    video_id: int


# --- Learn Module API Endpoints ---

@app.get("/api/learn/videos", response_model=List[LearnVideoResponse])
def get_learn_videos(
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db)
):
    """
    GET /api/learn/videos
    
    Returns a list of all available educational videos.
    Optionally filter by category.
    Videos are ordered by featured status first, then by order_index.
    """
    query = db.query(models.LearnVideo)
    
    if category:
        query = query.filter(models.LearnVideo.category == category)
    
    # Order by featured first, then by order_index
    videos = query.order_by(
        models.LearnVideo.is_featured.desc(),
        models.LearnVideo.order_index
    ).all()
    
    return videos


@app.get("/api/learn/categories", response_model=List[str])
def get_learn_categories(db: Session = Depends(get_db)):
    """
    GET /api/learn/categories
    
    Returns a list of unique video categories available.
    """
    categories = db.query(models.LearnVideo.category).distinct().all()
    return [cat[0] for cat in categories]


@app.post("/api/learn/seed", response_model=SimpleResponse)
def seed_learn_videos(db: Session = Depends(get_db)):
    """
    POST /api/learn/seed
    
    Seeds the database with initial educational videos.
    Only adds videos if the table is empty.
    Content focused on Indian finance and investing context.
    """
    # Check if videos already exist
    existing_count = db.query(models.LearnVideo).count()
    if existing_count > 0:
        return {"message": f"Database already has {existing_count} videos. Skipping seed."}
    
    # Educational videos about Indian finance, investing, and crypto
    seed_videos = [
        {
            "title": "Stock Market Basics for Beginners (Hindi)",
            "description": "Learn the fundamentals of the Indian stock market, including how NSE and BSE work, what are shares, and how to start investing.",
            "thumbnail_url": "https://img.youtube.com/vi/p7HKvqRI_Bo/maxresdefault.jpg",
            "youtube_video_id": "p7HKvqRI_Bo",
            "category": "Investing Basics",
            "duration_minutes": 15,
            "is_featured": True,
            "order_index": 1
        },
        {
            "title": "What is Mutual Fund? Explained in Simple Terms",
            "description": "Understand how mutual funds work in India, types of mutual funds, and how to choose the right one for your goals.",
            "thumbnail_url": "https://img.youtube.com/vi/UZgRHNvOXFk/maxresdefault.jpg",
            "youtube_video_id": "UZgRHNvOXFk",
            "category": "Mutual Funds",
            "duration_minutes": 12,
            "is_featured": True,
            "order_index": 2
        },
        {
            "title": "How to Start a SIP Investment",
            "description": "Step-by-step guide to starting your first Systematic Investment Plan (SIP) in India. Learn about SIP benefits and best practices.",
            "thumbnail_url": "https://img.youtube.com/vi/Xr3lBXPWw30/maxresdefault.jpg",
            "youtube_video_id": "Xr3lBXPWw30",
            "category": "Mutual Funds",
            "duration_minutes": 10,
            "is_featured": False,
            "order_index": 3
        },
        {
            "title": "Understanding Cryptocurrency & Bitcoin",
            "description": "A beginner's guide to cryptocurrency, blockchain technology, and Bitcoin. Learn how crypto works and the risks involved.",
            "thumbnail_url": "https://img.youtube.com/vi/rYQgy8QDEBI/maxresdefault.jpg",
            "youtube_video_id": "rYQgy8QDEBI",
            "category": "Crypto",
            "duration_minutes": 18,
            "is_featured": False,
            "order_index": 4
        },
        {
            "title": "Personal Finance 101: Budgeting Tips",
            "description": "Essential budgeting tips for young adults in India. Learn the 50/30/20 rule and how to manage your monthly expenses.",
            "thumbnail_url": "https://img.youtube.com/vi/HQzoZfc3GwQ/maxresdefault.jpg",
            "youtube_video_id": "HQzoZfc3GwQ",
            "category": "Budgeting",
            "duration_minutes": 8,
            "is_featured": True,
            "order_index": 5
        },
        {
            "title": "PPF vs FD vs Mutual Funds: Where to Invest?",
            "description": "Compare different investment options in India - Public Provident Fund, Fixed Deposits, and Mutual Funds. Which is best for you?",
            "thumbnail_url": "https://img.youtube.com/vi/cqf6VYLcPF0/maxresdefault.jpg",
            "youtube_video_id": "cqf6VYLcPF0",
            "category": "Investing Basics",
            "duration_minutes": 14,
            "is_featured": False,
            "order_index": 6
        },
        {
            "title": "How to Open a Demat Account",
            "description": "Complete guide to opening a Demat account in India. Understand the process, documents required, and best brokers.",
            "thumbnail_url": "https://img.youtube.com/vi/Km8B-Lx15tI/maxresdefault.jpg",
            "youtube_video_id": "Km8B-Lx15tI",
            "category": "Investing Basics",
            "duration_minutes": 11,
            "is_featured": False,
            "order_index": 7
        },
        {
            "title": "Tax Saving Options Under 80C",
            "description": "Learn about Section 80C tax deductions in India. ELSS, PPF, life insurance, and other tax-saving investments explained.",
            "thumbnail_url": "https://img.youtube.com/vi/PaYOHfOFCBg/maxresdefault.jpg",
            "youtube_video_id": "PaYOHfOFCBg",
            "category": "Tax Planning",
            "duration_minutes": 13,
            "is_featured": False,
            "order_index": 8
        },
        {
            "title": "Gold Investment in India: Physical vs Digital",
            "description": "Should you buy physical gold or invest in digital gold and Gold ETFs? Understand the pros and cons of each option.",
            "thumbnail_url": "https://img.youtube.com/vi/F_VLq0Gb8MQ/maxresdefault.jpg",
            "youtube_video_id": "F_VLq0Gb8MQ",
            "category": "Investing Basics",
            "duration_minutes": 9,
            "is_featured": False,
            "order_index": 9
        },
        {
            "title": "Emergency Fund: How Much Do You Need?",
            "description": "Learn why an emergency fund is crucial and how to calculate the right amount for your situation in the Indian context.",
            "thumbnail_url": "https://img.youtube.com/vi/fVToMS2Q3XQ/maxresdefault.jpg",
            "youtube_video_id": "fVToMS2Q3XQ",
            "category": "Budgeting",
            "duration_minutes": 7,
            "is_featured": False,
            "order_index": 10
        }
    ]
    
    # Add all videos to database
    for video_data in seed_videos:
        video = models.LearnVideo(**video_data)
        db.add(video)
    
    db.commit()
    
    return {"message": f"Successfully seeded {len(seed_videos)} educational videos!"}


@app.post("/api/learn/complete", response_model=SimpleResponse)
def complete_lesson(request: LessonCompleteRequest, db: Session = Depends(get_db)):
    """
    POST /api/learn/complete
    
    Rewards the user with 100 XP when they complete a lesson.
    Also updates their activity streak for gamification.
    """
    # Find the user by email
    user = db.query(models.User).filter(models.User.email == request.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Award XP
    user.xp = (user.xp or 0) + 100
    
    # Update streak for gamification
    update_user_streak(user, db)
    
    # Commit changes
    db.commit()
    
    return {"message": "Lesson completed! +100 XP earned."}


# ============================================================================
# PAPER TRADING SECTION (Indian Rupees ₹)
# ============================================================================

# --- Paper Trading Pydantic Schemas ---

class TradeRequest(BaseModel):
    """Request schema for executing a buy order."""
    asset_symbol: str = Field(..., description="Stock/crypto symbol (e.g., 'RELIANCE.NS', 'TCS.NS', 'BTC-INR')")
    quantity: float = Field(..., gt=0, description="Number of shares/units to buy")


class HoldingResponse(BaseModel):
    """Response schema for a single holding."""
    asset_symbol: str
    quantity: float
    average_buy_price: float
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_percent: Optional[float] = None

    class Config:
        orm_mode = True


class PortfolioSummaryResponse(BaseModel):
    """Response schema for portfolio summary with real-time valuations."""
    portfolio_id: int
    virtual_cash: float
    total_holdings_value: float
    total_portfolio_value: float
    holdings: List[HoldingResponse]
    
    class Config:
        orm_mode = True


class TradeExecutionResponse(BaseModel):
    """Response schema confirming a successful trade execution."""
    message: str
    asset_symbol: str
    quantity: float
    executed_price: float          # Price per share in ₹
    brokerage_fee: float           # 0.1% fee in ₹
    total_cost: float              # (price * qty) + fee in ₹
    remaining_cash: float
    new_holding_quantity: float
    new_average_price: float
    is_usd_converted: bool = False # True if USD stock was converted to INR
    usd_to_inr_rate: Optional[float] = None  # Exchange rate used (if applicable)


# --- Helper Function: Fetch Real-Time Price via yfinance ---

def get_current_price(symbol: str) -> Optional[float]:
    """
    Fetches the current market price for a given asset symbol using yfinance.
    Returns None if the symbol is invalid or data cannot be fetched.
    
    Handles common edge cases:
    - Invalid symbols
    - Network errors
    - Markets closed (uses last available price)
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        
        # Try to get fast info first (more reliable)
        info = ticker.fast_info
        
        # Prefer 'lastPrice' for real-time, fall back to 'previousClose'
        if hasattr(info, 'last_price') and info.last_price is not None:
            return float(info.last_price)
        elif hasattr(info, 'previous_close') and info.previous_close is not None:
            return float(info.previous_close)
        
        # Fallback: Get from history if fast_info fails
        hist = ticker.history(period="1d")
        if not hist.empty and 'Close' in hist.columns:
            return float(hist['Close'].iloc[-1])
        
        return None
        
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None


# Global ThreadPoolExecutor for non-blocking I/O operations
_executor = ThreadPoolExecutor(max_workers=10)


async def get_current_price_async(symbol: str) -> Optional[float]:
    """
    Async wrapper for get_current_price that runs yfinance in a thread pool.
    This prevents blocking the main FastAPI event loop during market data fetches.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, get_current_price, symbol)


def get_or_create_portfolio(user: models.User, db: Session) -> models.Portfolio:
    """
    Gets the user's portfolio, or creates one with initial ₹1,00,000 if it doesn't exist.
    This ensures lazy initialization of portfolios.
    """
    if user.portfolio:
        return user.portfolio
    
    # Create new portfolio with initial balance (1 Lakh Rupees)
    new_portfolio = models.Portfolio(
        user_id=user.id,
        virtual_cash=100000.0,
        created_at=datetime.utcnow()
    )
    db.add(new_portfolio)
    db.commit()
    db.refresh(new_portfolio)
    
    return new_portfolio


# =============================================================================
# TRADING ENGINE HELPER FUNCTIONS
# =============================================================================

# --- Currency Conversion Cache (Short TTL for near real-time) ---
_usd_inr_cache = {"rate": 87.50, "timestamp": None}

def get_usd_to_inr_rate() -> float:
    """
    Fetch LIVE USD/INR exchange rate from a public API.
    
    Uses open.er-api.com for reliable exchange rates with a 1-minute cache.
    Falls back to static rate if API fails.
    Default fallback: 84.50 (approximate current rate).
    """
    global _usd_inr_cache
    
    # Return cached rate if fresh (within 1 minute for near real-time)
    if _usd_inr_cache["timestamp"]:
        cache_age = datetime.utcnow() - _usd_inr_cache["timestamp"]
        if cache_age < timedelta(minutes=1):
            print(f"💵 USD/INR (cached): {_usd_inr_cache['rate']:.2f}")
            return _usd_inr_cache["rate"]
    
    try:
        # Use open.er-api.com public API (no auth required, 1500 requests/month free)
        response = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("result") == "success" and "rates" in data:
                rate = float(data["rates"]["INR"])
                _usd_inr_cache = {"rate": rate, "timestamp": datetime.utcnow()}
                print(f"🔥 LIVE USD RATE: {rate:.4f} (er-api.com)")
                return rate
        
        print(f"⚠️ USD/INR API returned status: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("⚠️ USD/INR API timeout")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ USD/INR API error: {e}")
    except Exception as e:
        print(f"⚠️ USD/INR fetch error: {e}")
    
    # Return cached or default fallback
    print(f"⚠️ USD/INR using fallback: {_usd_inr_cache['rate']:.2f}")
    return _usd_inr_cache["rate"]


def is_market_open(symbol: str) -> bool:
    """
    Check if the market is open for trading the given symbol.
    
    Rules:
    - Indian stocks (.NS, .BO): 9:15 AM - 3:30 PM IST, weekdays only
    - Crypto (-USD, -INR): Always open (24/7)
    - US stocks: Allow 24/7 for paper trading simplicity
    """
    import pytz
    
    symbol_upper = symbol.upper()
    
    # Crypto is always open (24/7 market)
    if "-USD" in symbol_upper or "-INR" in symbol_upper:
        return True
    
    # Indian stocks - enforce NSE/BSE market hours
    if symbol_upper.endswith(".NS") or symbol_upper.endswith(".BO"):
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)
        
        # Check if weekday (Monday = 0, Sunday = 6)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check time (9:15 AM to 3:30 PM IST)
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    # US stocks - allow 24/7 for paper trading (currency conversion still applies)
    return True


def is_us_stock(symbol: str) -> bool:
    """
    Determine if a symbol is a US stock (not Indian, not crypto).
    US stocks need USD to INR conversion.
    """
    symbol_upper = symbol.upper()
    
    # Indian stock suffixes - NOT a US stock
    if symbol_upper.endswith(".NS") or symbol_upper.endswith(".BO"):
        return False
    
    # Crypto patterns - NOT a US stock
    if "-USD" in symbol_upper or "-INR" in symbol_upper:
        return False
    
    # Everything else is a US stock
    return True


# Brokerage fee rate (0.1%)
BROKERAGE_FEE_RATE = 0.001


# --- Paper Trading API Endpoints ---

@app.get("/api/trade/portfolio", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(email: str = Query(...), db: Session = Depends(get_db)):
    """
    GET /api/trade/portfolio
    
    Fetches the user's complete portfolio summary including:
    - Virtual cash balance
    - All holdings with real-time valuations (converted to INR for US stocks)
    - Total portfolio value (cash + holdings)
    - Profit/loss calculations for each holding
    
    Uses async/await with ThreadPoolExecutor for non-blocking price fetches.
    If the user doesn't have a portfolio, one is created with ₹1,00,000.
    
    IMPORTANT: US stock prices are automatically converted from USD to INR
    to match the INR-denominated average_buy_price stored in the database.
    """
    # Find user by email
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get or create portfolio
    portfolio = get_or_create_portfolio(user, db)
    
    # Fetch the USD to INR rate once for all US stock conversions
    usd_to_inr = get_usd_to_inr_rate()
    
    # Fetch all prices concurrently using asyncio.gather
    holdings = portfolio.holdings
    if holdings:
        price_tasks = [get_current_price_async(h.asset_symbol) for h in holdings]
        prices = await asyncio.gather(*price_tasks)
    else:
        prices = []
    
    # Build holdings response with fetched prices
    holdings_response: List[HoldingResponse] = []
    total_holdings_value = 0.0
    
    for holding, raw_price in zip(holdings, prices):
        if raw_price is not None:
            # Convert USD to INR for US stocks to match stored average_buy_price (INR)
            if is_us_stock(holding.asset_symbol):
                price_inr = raw_price * usd_to_inr
                print(f"[Portfolio] US Stock {holding.asset_symbol}: ${raw_price:.2f} → ₹{price_inr:.2f}")
            else:
                price_inr = raw_price
            
            current_value = price_inr * holding.quantity
            cost_basis = holding.average_buy_price * holding.quantity
            profit_loss = current_value - cost_basis
            profit_loss_percent = ((price_inr - holding.average_buy_price) / holding.average_buy_price) * 100 if holding.average_buy_price > 0 else 0.0
            total_holdings_value += current_value
            current_price = price_inr
        else:
            # If price fetch fails, use average buy price as fallback
            current_value = holding.average_buy_price * holding.quantity
            current_price = holding.average_buy_price
            profit_loss = 0.0
            profit_loss_percent = 0.0
            total_holdings_value += current_value
        
        holdings_response.append(HoldingResponse(
            asset_symbol=holding.asset_symbol,
            quantity=holding.quantity,
            average_buy_price=round(holding.average_buy_price, 2),
            current_price=round(current_price, 2) if current_price else None,
            current_value=round(current_value, 2),
            profit_loss=round(profit_loss, 2),
            profit_loss_percent=round(profit_loss_percent, 2)
        ))
    
    total_portfolio_value = portfolio.virtual_cash + total_holdings_value
    
    return PortfolioSummaryResponse(
        portfolio_id=portfolio.id,
        virtual_cash=round(portfolio.virtual_cash, 2),
        total_holdings_value=round(total_holdings_value, 2),
        total_portfolio_value=round(total_portfolio_value, 2),
        holdings=holdings_response
    )


@app.get("/api/trade/holdings", response_model=List[HoldingResponse])
def get_holdings(email: str = Query(...), db: Session = Depends(get_db)):
    """
    GET /api/trade/holdings
    
    Returns a simple list of all assets the user currently owns.
    Shows symbol, quantity, and average buy price.
    Does NOT fetch real-time prices (for performance).
    """
    # Find user by email
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get or create portfolio
    portfolio = get_or_create_portfolio(user, db)
    
    # Return holdings without real-time price data
    holdings_response = []
    for holding in portfolio.holdings:
        holdings_response.append(HoldingResponse(
            asset_symbol=holding.asset_symbol,
            quantity=holding.quantity,
            average_buy_price=round(holding.average_buy_price, 2)
        ))
    
    return holdings_response


@app.post("/api/trade/buy", response_model=TradeExecutionResponse)
def execute_buy_order(
    trade: TradeRequest, 
    email: str = Query(...), 
    db: Session = Depends(get_db)
):
    """
    POST /api/trade/buy
    
    Executes a buy order for the specified asset with realistic trading features:
    1. Validates market hours (Indian stocks: 9:15 AM - 3:30 PM IST weekdays)
    2. Fetches current real-time price via yfinance
    3. Converts USD to INR for US stocks
    4. Calculates 0.1% brokerage fee
    5. Validates user has sufficient virtual cash
    6. Deducts cost + fee from portfolio cash
    7. Updates existing holding (with weighted average price) or creates new one
    8. Logs transaction in the Transaction ledger
    9. Returns execution confirmation with fee details
    
    Uses proper transaction handling to ensure data integrity.
    """
    # Find user by email
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get or create portfolio
    portfolio = get_or_create_portfolio(user, db)
    
    # Normalize symbol to uppercase
    symbol = trade.asset_symbol.upper().strip()
    quantity = trade.quantity
    
    # --- Step 1: Validate Market Hours ---
    if not is_market_open(symbol):
        raise HTTPException(
            status_code=400,
            detail=f"Market is Closed. Indian stocks can only be traded between 9:15 AM - 3:30 PM IST on weekdays."
        )
    
    # --- Step 2: Fetch current market price ---
    raw_price = get_current_price(symbol)
    
    if raw_price is None:
        raise HTTPException(
            status_code=400, 
            detail=f"Unable to fetch price for symbol '{symbol}'. Please verify the symbol is valid (e.g., 'RELIANCE.NS' for Reliance, 'TCS.NS' for TCS, 'BTC-INR' for Bitcoin in INR)."
        )
    
    if raw_price <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid price received for symbol '{symbol}'. Please try again."
        )
    
    # --- Step 3: Currency Conversion (for US stocks) ---
    is_usd = is_us_stock(symbol)
    usd_rate = None
    
    if is_usd:
        usd_rate = get_usd_to_inr_rate()
        price_inr = raw_price * usd_rate
        print(f"[Trading] US Stock detected. Converted ${raw_price:.2f} USD → ₹{price_inr:.2f} INR (rate: {usd_rate})")
    else:
        price_inr = raw_price
    
    # --- Step 4: Calculate costs with brokerage fee ---
    trade_value = price_inr * quantity
    brokerage_fee = trade_value * BROKERAGE_FEE_RATE
    total_cost = trade_value + brokerage_fee
    
    # --- Step 5: Validate funds ---
    if total_cost > portfolio.virtual_cash:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Required: ₹{total_cost:,.2f} (incl. ₹{brokerage_fee:.2f} brokerage), Available: ₹{portfolio.virtual_cash:,.2f}"
        )
    
    # --- Step 6: Execute the trade (transactional) ---
    try:
        # Deduct total cost (including fee) from portfolio
        portfolio.virtual_cash -= total_cost
        
        # Check if user already owns this asset
        existing_holding = db.query(models.Holding).filter(
            models.Holding.portfolio_id == portfolio.id,
            models.Holding.asset_symbol == symbol
        ).first()
        
        if existing_holding:
            # --- Update existing holding with weighted average price ---
            # Formula: new_avg = (old_qty * old_avg + new_qty * new_price) / (old_qty + new_qty)
            old_value = existing_holding.quantity * existing_holding.average_buy_price
            new_value = quantity * price_inr
            new_total_quantity = existing_holding.quantity + quantity
            
            new_average_price = (old_value + new_value) / new_total_quantity
            
            existing_holding.quantity = new_total_quantity
            existing_holding.average_buy_price = new_average_price
            
            final_quantity = new_total_quantity
            final_avg_price = new_average_price
        else:
            # --- Create new holding ---
            new_holding = models.Holding(
                portfolio_id=portfolio.id,
                asset_symbol=symbol,
                quantity=quantity,
                average_buy_price=price_inr
            )
            db.add(new_holding)
            
            final_quantity = quantity
            final_avg_price = price_inr
        
        # --- Step 7: Create Transaction Record ---
        transaction = models.Transaction(
            user_id=user.id,
            symbol=symbol,
            type="BUY",
            quantity=quantity,
            price_per_share=price_inr,
            total_amount=trade_value,
            brokerage_fee=brokerage_fee,
            timestamp=datetime.utcnow()
        )
        db.add(transaction)
        
        # Commit the transaction
        db.commit()
        
        # --- GAMIFICATION: Update streak and check achievements ---
        update_user_streak(user, db)
        
        # Check for first trade achievement
        total_trades = len(portfolio.holdings)
        if total_trades == 1 and not existing_holding:
            check_and_award_achievement(user, "first_trade", db)
        
        # Check for diversifier achievement (5+ different stocks)
        if total_trades >= 5:
            check_and_award_achievement(user, "diversifier", db)
        
        # Check streak achievements
        if user.current_streak >= 7:
            check_and_award_achievement(user, "week_streak", db)
        if user.current_streak >= 30:
            check_and_award_achievement(user, "month_streak", db)
        # ---------------------------------------------------------
        
        return TradeExecutionResponse(
            message=f"Successfully purchased {quantity} units of {symbol}",
            asset_symbol=symbol,
            quantity=quantity,
            executed_price=round(price_inr, 2),
            brokerage_fee=round(brokerage_fee, 2),
            total_cost=round(total_cost, 2),
            remaining_cash=round(portfolio.virtual_cash, 2),
            new_holding_quantity=round(final_quantity, 4),
            new_average_price=round(final_avg_price, 2),
            is_usd_converted=is_usd,
            usd_to_inr_rate=round(usd_rate, 2) if usd_rate else None
        )
        
    except Exception as e:
        # Rollback on any error to maintain data integrity
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Trade execution failed: {str(e)}"
        )


# --- SELL ASSET ENDPOINT ---

class SellRequest(BaseModel):
    """Request schema for selling an asset."""
    email: str
    symbol: str
    quantity: float = Field(..., gt=0, description="Number of shares/units to sell")


class SellExecutionResponse(BaseModel):
    """Response schema for successful sell order execution."""
    message: str
    asset_symbol: str
    quantity_sold: float
    executed_price: float           # Price per share in ₹
    gross_proceeds: float           # Price × Quantity in ₹
    brokerage_fee: float            # 0.1% fee in ₹
    net_proceeds: float             # Amount added to cash after fee
    remaining_cash: float
    remaining_quantity: float       # Remaining holding quantity (0 if fully sold)
    is_usd_converted: bool = False
    usd_to_inr_rate: Optional[float] = None


@app.post("/api/trade/sell", response_model=SellExecutionResponse)
def sell_asset(request: SellRequest, db: Session = Depends(get_db)):
    """
    POST /api/trade/sell
    
    Sells a specified quantity of an asset from the user's portfolio with realistic trading:
    1. Validates market hours (Indian stocks: 9:15 AM - 3:30 PM IST weekdays)
    2. Validates user owns the asset and has sufficient quantity
    3. Fetches current market price from Yahoo Finance
    4. Converts USD to INR for US stocks
    5. Calculates 0.1% brokerage fee (deducted from proceeds)
    6. Increases virtual cash balance by net proceeds (after fee)
    7. Updates or removes the holding
    8. Logs transaction in the Transaction ledger
    
    Returns execution details including proceeds, fee, and remaining position.
    """
    email = request.email.lower().strip()
    symbol = request.symbol.upper().strip()
    quantity = request.quantity
    
    # Find user
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get portfolio
    if not user.portfolio:
        raise HTTPException(status_code=400, detail="No portfolio found. You need to buy assets first.")
    
    portfolio = user.portfolio
    
    # --- Validate Market Hours ---
    if not is_market_open(symbol):
        raise HTTPException(
            status_code=400,
            detail=f"Market is Closed. Indian stocks can only be traded between 9:15 AM - 3:30 PM IST on weekdays."
        )
    
    # Find the holding
    holding = db.query(models.Holding).filter(
        models.Holding.portfolio_id == portfolio.id,
        models.Holding.asset_symbol == symbol
    ).first()
    
    if not holding:
        raise HTTPException(
            status_code=400,
            detail=f"You don't own any {symbol}. Cannot sell."
        )
    
    # Check if user has enough quantity
    if holding.quantity < quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient holdings. You own {holding.quantity:.4f} {symbol}, but tried to sell {quantity:.4f}."
        )
    
    # Get current market price
    raw_price = get_current_price(symbol)
    if raw_price is None:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to fetch current price for {symbol}. Market may be closed or symbol is invalid."
        )
    
    # --- Currency Conversion (for US stocks) ---
    is_usd = is_us_stock(symbol)
    usd_rate = None
    
    if is_usd:
        usd_rate = get_usd_to_inr_rate()
        price_inr = raw_price * usd_rate
        print(f"[Trading] US Stock sell. Converted ${raw_price:.2f} USD → ₹{price_inr:.2f} INR (rate: {usd_rate})")
    else:
        price_inr = raw_price
    
    try:
        # --- Calculate proceeds with brokerage fee ---
        gross_proceeds = price_inr * quantity
        brokerage_fee = gross_proceeds * BROKERAGE_FEE_RATE
        net_proceeds = gross_proceeds - brokerage_fee
        
        # Update cash balance (net of fee)
        portfolio.virtual_cash += net_proceeds
        
        # Update or remove holding
        if holding.quantity == quantity:
            # Selling entire position - remove holding
            db.delete(holding)
            remaining_quantity = 0.0
        else:
            # Partial sell - update quantity (average price stays the same)
            holding.quantity -= quantity
            remaining_quantity = holding.quantity
        
        # --- Create Transaction Record ---
        transaction = models.Transaction(
            user_id=user.id,
            symbol=symbol,
            type="SELL",
            quantity=quantity,
            price_per_share=price_inr,
            total_amount=gross_proceeds,
            brokerage_fee=brokerage_fee,
            timestamp=datetime.utcnow()
        )
        db.add(transaction)
        
        # Commit transaction
        db.commit()
        
        return SellExecutionResponse(
            message=f"Successfully sold {quantity} units of {symbol}",
            asset_symbol=symbol,
            quantity_sold=quantity,
            executed_price=round(price_inr, 2),
            gross_proceeds=round(gross_proceeds, 2),
            brokerage_fee=round(brokerage_fee, 2),
            net_proceeds=round(net_proceeds, 2),
            remaining_cash=round(portfolio.virtual_cash, 2),
            remaining_quantity=round(remaining_quantity, 4),
            is_usd_converted=is_usd,
            usd_to_inr_rate=round(usd_rate, 2) if usd_rate else None
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Sell order failed: {str(e)}"
        )


# --- TRANSACTION HISTORY ENDPOINT ---

class TransactionResponse(BaseModel):
    """Response schema for transaction history."""
    id: int
    symbol: str
    type: str               # "BUY" or "SELL"
    quantity: float
    price_per_share: float  # In ₹
    total_amount: float     # In ₹
    brokerage_fee: float    # In ₹
    timestamp: str          # Formatted datetime

    class Config:
        orm_mode = True


@app.get("/api/trade/history", response_model=List[TransactionResponse])
def get_transaction_history(email: str = Query(...), db: Session = Depends(get_db)):
    """
    GET /api/trade/history
    
    Returns the list of all transactions for the logged-in user.
    Ordered by timestamp descending (newest first).
    
    Each transaction includes:
    - Symbol traded
    - Transaction type (BUY/SELL)
    - Quantity
    - Price per share (in ₹)
    - Total amount (in ₹)
    - Brokerage fee (in ₹)
    - Timestamp
    """
    # Find user by email
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Fetch transactions ordered by timestamp descending
    transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id == user.id
    ).order_by(models.Transaction.timestamp.desc()).all()
    
    # Format response
    result = []
    for txn in transactions:
        result.append(TransactionResponse(
            id=txn.id,
            symbol=txn.symbol,
            type=txn.type,
            quantity=txn.quantity,
            price_per_share=round(txn.price_per_share, 2),
            total_amount=round(txn.total_amount, 2),
            brokerage_fee=round(txn.brokerage_fee, 2),
            timestamp=txn.timestamp.strftime("%b %d, %Y %I:%M %p")
        ))
    
    return result

# --- Additional Utility Endpoint: Get Asset Price ---

class AssetPriceResponse(BaseModel):
    """Response schema for asset price lookup."""
    symbol: str
    current_price: Optional[float]      # Price in ₹ (converted if USD)
    currency: str = "INR"               # Always INR for consistency
    source: str = "Yahoo Finance"
    is_usd_converted: bool = False      # True if price was converted from USD
    usd_to_inr_rate: Optional[float] = None  # Conversion rate if applicable
    original_usd_price: Optional[float] = None  # Original USD price if converted


@app.get("/api/trade/price/{symbol}", response_model=AssetPriceResponse)
def get_asset_price(symbol: str):
    """
    GET /api/trade/price/{symbol}
    
    Utility endpoint to look up the current price of any asset.
    Useful for the frontend to display prices before placing an order.
    
    IMPORTANT: For US stocks (AAPL, TSLA, etc.), the price is automatically
    converted from USD to INR using the live exchange rate.
    This ensures consistency - all prices shown in the app are in ₹.
    """
    normalized_symbol = symbol.upper().strip()
    raw_price = get_current_price(normalized_symbol)
    
    if raw_price is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find price for symbol '{normalized_symbol}'. Please verify the symbol is valid."
        )
    
    # Check if this is a US stock that needs conversion
    is_usd = is_us_stock(normalized_symbol)
    usd_rate = None
    original_usd = None
    
    if is_usd:
        usd_rate = get_usd_to_inr_rate()
        original_usd = raw_price
        price_inr = raw_price * usd_rate
        print(f"[Price API] US Stock {normalized_symbol}: ${raw_price:.2f} USD → ₹{price_inr:.2f} INR (rate: {usd_rate})")
    else:
        price_inr = raw_price
    
    return AssetPriceResponse(
        symbol=normalized_symbol,
        current_price=round(price_inr, 2),
        currency="INR",
        is_usd_converted=is_usd,
        usd_to_inr_rate=round(usd_rate, 2) if usd_rate else None,
        original_usd_price=round(original_usd, 2) if original_usd else None
    )


# --- Price History Endpoint (for charts) ---

class PricePoint(BaseModel):
    """Single price point for charting."""
    timestamp: int  # Unix timestamp in milliseconds
    price: float    # Price in ₹ (converted if USD stock)

class PriceHistoryResponse(BaseModel):
    """Response schema for price history data."""
    symbol: str
    period: str
    data: List[PricePoint]
    price_change: float             # In ₹
    price_change_percent: float
    current_price: float            # In ₹
    previous_close: float           # In ₹
    is_usd_converted: bool = False
    usd_to_inr_rate: Optional[float] = None


@app.get("/api/trade/history/{symbol}", response_model=PriceHistoryResponse)
def get_price_history(symbol: str, period: str = Query("1d", regex="^(1d|1w|1m)$")):
    """
    GET /api/trade/history/{symbol}?period=1d
    
    Fetches historical price data for charting.
    
    Periods:
    - 1d: Last 1 day (5-minute intervals)
    - 1w: Last 1 week (1-hour intervals)  
    - 1m: Last 1 month (1-day intervals)
    
    Returns list of {timestamp, price} for charting plus change statistics.
    All prices are returned in INR (USD stocks are automatically converted).
    """
    try:
        normalized_symbol = symbol.upper().strip()
        ticker = yf.Ticker(normalized_symbol)
        
        # Check if this is a US stock that needs conversion
        is_usd = is_us_stock(normalized_symbol)
        usd_rate = get_usd_to_inr_rate() if is_usd else None
        
        # Map period to yfinance parameters
        period_map = {
            "1d": ("1d", "5m"),   # 1 day, 5-min intervals
            "1w": ("5d", "1h"),   # 5 days (trading week), 1-hour intervals
            "1m": ("1mo", "1d")   # 1 month, daily intervals
        }
        
        yf_period, yf_interval = period_map.get(period, ("1d", "5m"))
        
        # Fetch historical data
        hist = ticker.history(period=yf_period, interval=yf_interval)
        
        if hist.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No price history found for symbol '{normalized_symbol}'"
            )
        
        # Convert to list of price points (with INR conversion if needed)
        data_points = []
        for index, row in hist.iterrows():
            timestamp_ms = int(index.timestamp() * 1000)
            raw_price = float(row['Close'])
            price_inr = raw_price * usd_rate if is_usd else raw_price
            data_points.append(PricePoint(
                timestamp=timestamp_ms,
                price=round(price_inr, 2)
            ))
        
        # Calculate price change (already in INR)
        if len(data_points) >= 2:
            first_price = data_points[0].price
            current_price = data_points[-1].price
            price_change = current_price - first_price
            price_change_percent = (price_change / first_price) * 100 if first_price > 0 else 0
        else:
            current_price = data_points[-1].price if data_points else 0
            price_change = 0
            price_change_percent = 0
            first_price = current_price
        
        if is_usd:
            print(f"[History API] US Stock {normalized_symbol}: Converted {len(data_points)} points to INR (rate: {usd_rate})")
        
        return PriceHistoryResponse(
            symbol=normalized_symbol,
            period=period,
            data=data_points,
            price_change=round(price_change, 2),
            price_change_percent=round(price_change_percent, 2),
            current_price=round(current_price, 2),
            previous_close=round(first_price, 2),
            is_usd_converted=is_usd,
            usd_to_inr_rate=round(usd_rate, 2) if usd_rate else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching price history for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch price history: {str(e)}"
        )


# --- Stock Search Endpoint (Groww-style name search) ---

class StockSearchResult(BaseModel):
    """Response schema for stock search results."""
    name: str
    symbol: str
    exchange: Optional[str] = None


@app.get("/api/trade/search", response_model=List[StockSearchResult])
def search_stocks(query: str = Query(..., min_length=1, description="Search query for stock name or symbol")):
    """
    GET /api/trade/search?query=reliance
    
    Searches for stocks by company name or symbol.
    Returns matching stocks with their display names and base symbols.
    For Indian stocks, returns the base symbol without .NS/.BO suffix.
    
    Examples:
    - query=Reliance -> Returns "Reliance Industries" with symbol "RELIANCE"  
    - query=Apple -> Returns "Apple Inc." with symbol "AAPL"
    - query=TCS -> Returns "Tata Consultancy Services" with symbol "TCS"
    """
    try:
        import yfinance as yf
        
        results: List[StockSearchResult] = []
        query_upper = query.upper().strip()
        query_lower = query.lower().strip()
        
        # Popular Indian stocks mapping (for quick lookup)
        indian_stocks = {
            "reliance": ("Reliance Industries", "RELIANCE"),
            "tcs": ("Tata Consultancy Services", "TCS"),
            "infosys": ("Infosys Ltd", "INFY"),
            "infy": ("Infosys Ltd", "INFY"),
            "hdfc": ("HDFC Bank", "HDFCBANK"),
            "hdfcbank": ("HDFC Bank", "HDFCBANK"),
            "icici": ("ICICI Bank", "ICICIBANK"),
            "icicibank": ("ICICI Bank", "ICICIBANK"),
            "sbi": ("State Bank of India", "SBIN"),
            "sbin": ("State Bank of India", "SBIN"),
            "bharti": ("Bharti Airtel", "BHARTIARTL"),
            "airtel": ("Bharti Airtel", "BHARTIARTL"),
            "itc": ("ITC Ltd", "ITC"),
            "wipro": ("Wipro Ltd", "WIPRO"),
            "hcl": ("HCL Technologies", "HCLTECH"),
            "hcltech": ("HCL Technologies", "HCLTECH"),
            "kotak": ("Kotak Mahindra Bank", "KOTAKBANK"),
            "kotakbank": ("Kotak Mahindra Bank", "KOTAKBANK"),
            "axis": ("Axis Bank", "AXISBANK"),
            "axisbank": ("Axis Bank", "AXISBANK"),
            "maruti": ("Maruti Suzuki", "MARUTI"),
            "bajaj": ("Bajaj Finance", "BAJFINANCE"),
            "bajfinance": ("Bajaj Finance", "BAJFINANCE"),
            "titan": ("Titan Company", "TITAN"),
            "asian": ("Asian Paints", "ASIANPAINT"),
            "asianpaint": ("Asian Paints", "ASIANPAINT"),
            "lt": ("Larsen & Toubro", "LT"),
            "larsen": ("Larsen & Toubro", "LT"),
            "tata": ("Tata Motors", "TATAMOTORS"),
            "tatamotors": ("Tata Motors", "TATAMOTORS"),
            "tatasteel": ("Tata Steel", "TATASTEEL"),
            "sunpharma": ("Sun Pharma", "SUNPHARMA"),
            "sun": ("Sun Pharma", "SUNPHARMA"),
            "powergrid": ("Power Grid Corp", "POWERGRID"),
            "ntpc": ("NTPC Ltd", "NTPC"),
            "ongc": ("ONGC", "ONGC"),
            "coal": ("Coal India", "COALINDIA"),
            "coalindia": ("Coal India", "COALINDIA"),
            "adani": ("Adani Enterprises", "ADANIENT"),
            "adanient": ("Adani Enterprises", "ADANIENT"),
            "adaniports": ("Adani Ports", "ADANIPORTS"),
            "ultracemco": ("UltraTech Cement", "ULTRACEMCO"),
            "ultratech": ("UltraTech Cement", "ULTRACEMCO"),
            "jswsteel": ("JSW Steel", "JSWSTEEL"),
            "jsw": ("JSW Steel", "JSWSTEEL"),
            "hindalco": ("Hindalco Industries", "HINDALCO"),
            "techm": ("Tech Mahindra", "TECHM"),
            "tech mahindra": ("Tech Mahindra", "TECHM"),
            "drreddy": ("Dr. Reddy's Labs", "DRREDDY"),
            "cipla": ("Cipla Ltd", "CIPLA"),
            "divislab": ("Divi's Laboratories", "DIVISLAB"),
            "divi": ("Divi's Laboratories", "DIVISLAB"),
            "britannia": ("Britannia Industries", "BRITANNIA"),
            "nestle": ("Nestle India", "NESTLEIND"),
            "nestleind": ("Nestle India", "NESTLEIND"),
            "hindunilvr": ("Hindustan Unilever", "HINDUNILVR"),
            "hul": ("Hindustan Unilever", "HINDUNILVR"),
            "unilever": ("Hindustan Unilever", "HINDUNILVR"),
        }
        
        # Popular US stocks mapping
        us_stocks = {
            "apple": ("Apple Inc.", "AAPL"),
            "aapl": ("Apple Inc.", "AAPL"),
            "microsoft": ("Microsoft Corp", "MSFT"),
            "msft": ("Microsoft Corp", "MSFT"),
            "google": ("Alphabet Inc.", "GOOGL"),
            "googl": ("Alphabet Inc.", "GOOGL"),
            "alphabet": ("Alphabet Inc.", "GOOGL"),
            "amazon": ("Amazon.com Inc.", "AMZN"),
            "amzn": ("Amazon.com Inc.", "AMZN"),
            "tesla": ("Tesla Inc.", "TSLA"),
            "tsla": ("Tesla Inc.", "TSLA"),
            "meta": ("Meta Platforms", "META"),
            "facebook": ("Meta Platforms", "META"),
            "nvidia": ("NVIDIA Corp", "NVDA"),
            "nvda": ("NVIDIA Corp", "NVDA"),
            "netflix": ("Netflix Inc.", "NFLX"),
            "nflx": ("Netflix Inc.", "NFLX"),
            "amd": ("Advanced Micro Devices", "AMD"),
            "intel": ("Intel Corp", "INTC"),
            "intc": ("Intel Corp", "INTC"),
            "disney": ("Walt Disney Co", "DIS"),
            "dis": ("Walt Disney Co", "DIS"),
            "spotify": ("Spotify Technology", "SPOT"),
            "spot": ("Spotify Technology", "SPOT"),
            "paypal": ("PayPal Holdings", "PYPL"),
            "pypl": ("PayPal Holdings", "PYPL"),
            "adobe": ("Adobe Inc.", "ADBE"),
            "adbe": ("Adobe Inc.", "ADBE"),
            "salesforce": ("Salesforce Inc.", "CRM"),
            "crm": ("Salesforce Inc.", "CRM"),
            "visa": ("Visa Inc.", "V"),
            "mastercard": ("Mastercard Inc.", "MA"),
            "jpmorgan": ("JPMorgan Chase", "JPM"),
            "jpm": ("JPMorgan Chase", "JPM"),
            "goldman": ("Goldman Sachs", "GS"),
            "gs": ("Goldman Sachs", "GS"),
            "berkshire": ("Berkshire Hathaway", "BRK-B"),
            "walmart": ("Walmart Inc.", "WMT"),
            "wmt": ("Walmart Inc.", "WMT"),
            "coca": ("Coca-Cola Co", "KO"),
            "ko": ("Coca-Cola Co", "KO"),
            "pepsi": ("PepsiCo Inc.", "PEP"),
            "pep": ("PepsiCo Inc.", "PEP"),
        }
        
        # Crypto mapping
        crypto = {
            "bitcoin": ("Bitcoin", "BTC-INR"),
            "btc": ("Bitcoin", "BTC-INR"),
            "ethereum": ("Ethereum", "ETH-INR"),
            "eth": ("Ethereum", "ETH-INR"),
            "dogecoin": ("Dogecoin", "DOGE-INR"),
            "doge": ("Dogecoin", "DOGE-INR"),
        }
        
        added_symbols = set()
        
        # Search in Indian stocks first
        for key, (name, symbol) in indian_stocks.items():
            if query_lower in key or query_lower in name.lower():
                if symbol not in added_symbols:
                    results.append(StockSearchResult(
                        name=name,
                        symbol=symbol,
                        exchange="NSE/BSE"
                    ))
                    added_symbols.add(symbol)
        
        # Search in US stocks
        for key, (name, symbol) in us_stocks.items():
            if query_lower in key or query_lower in name.lower():
                if symbol not in added_symbols:
                    results.append(StockSearchResult(
                        name=name,
                        symbol=symbol,
                        exchange="US"
                    ))
                    added_symbols.add(symbol)
        
        # Search in crypto
        for key, (name, symbol) in crypto.items():
            if query_lower in key or query_lower in name.lower():
                if symbol not in added_symbols:
                    results.append(StockSearchResult(
                        name=name,
                        symbol=symbol,
                        exchange="Crypto"
                    ))
                    added_symbols.add(symbol)
        
        # If no results found, try direct symbol lookup via yfinance
        if not results:
            try:
                # Try as NSE stock
                ticker_nse = yf.Ticker(f"{query_upper}.NS")
                info = ticker_nse.fast_info
                if hasattr(info, 'last_price') and info.last_price is not None:
                    results.append(StockSearchResult(
                        name=query_upper,
                        symbol=query_upper,
                        exchange="NSE/BSE"
                    ))
            except:
                pass
            
            # Try as US stock
            if not results:
                try:
                    ticker_us = yf.Ticker(query_upper)
                    info = ticker_us.fast_info
                    if hasattr(info, 'last_price') and info.last_price is not None:
                        results.append(StockSearchResult(
                            name=query_upper,
                            symbol=query_upper,
                            exchange="US"
                        ))
                except:
                    pass
        
        # Limit results to top 10
        return results[:10]
        
    except Exception as e:
        print(f"Search error: {e}")
        return []


# --- Reset Portfolio Endpoint (for testing/demo purposes) ---

@app.post("/api/trade/reset", response_model=SimpleResponse)
def reset_portfolio(email: str = Query(...), db: Session = Depends(get_db)):
    """
    POST /api/trade/reset
    
    Resets the user's portfolio to initial state:
    - Virtual cash back to ₹1,00,000 (1 Lakh Rupees)
    - All holdings deleted
    
    Useful for testing or allowing users to start fresh.
    """
    # Find user by email
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get portfolio
    portfolio = get_or_create_portfolio(user, db)
    
    # Delete all holdings
    db.query(models.Holding).filter(models.Holding.portfolio_id == portfolio.id).delete()
    
    # Reset cash to initial amount (1 Lakh Rupees)
    portfolio.virtual_cash = 100000.0
    
    db.commit()
    
    return {"message": "Portfolio reset to initial state. You have ₹1,00,000 to trade!"}


# =============================================================================
# GAMIFICATION API ENDPOINTS
# =============================================================================

class GamificationResponse(BaseModel):
    """Complete gamification status for a user."""
    xp: int
    level: int
    level_title: str
    progress_to_next: float  # 0.0 to 1.0
    xp_for_next_level: int
    current_streak: int
    earned_achievements: List[str]  # List of achievement keys


class AchievementDefResponse(BaseModel):
    """Achievement definition for display."""
    key: str
    name: str
    description: str
    xp_reward: int
    icon_name: str


@app.get("/api/user/gamification/{email}", response_model=GamificationResponse)
def get_user_gamification(email: str, db: Session = Depends(get_db)):
    """
    GET /api/user/gamification/{email}
    
    Returns complete gamification status including:
    - XP and level info
    - Streak count
    - List of earned achievement keys
    """
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Calculate level
    level_info = calculate_level(user.xp or 0)
    
    # Get earned achievements
    earned = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == user.id
    ).all()
    
    earned_keys = []
    for ua in earned:
        achievement = db.query(models.Achievement).filter(
            models.Achievement.id == ua.achievement_id
        ).first()
        if achievement:
            earned_keys.append(achievement.key)
    
    return GamificationResponse(
        xp=user.xp or 0,
        level=level_info["level"],
        level_title=level_info["title"],
        progress_to_next=level_info["progress_to_next"],
        xp_for_next_level=level_info["xp_for_next_level"],
        current_streak=user.current_streak or 0,
        earned_achievements=earned_keys
    )


@app.get("/api/achievements/all", response_model=List[AchievementDefResponse])
def get_all_achievements(db: Session = Depends(get_db)):
    """
    GET /api/achievements/all
    
    Returns all available achievements for trophy case display.
    """
    achievements = db.query(models.Achievement).all()
    return [
        AchievementDefResponse(
            key=a.key,
            name=a.name,
            description=a.description,
            xp_reward=a.xp_reward,
            icon_name=a.icon_name
        )
        for a in achievements
    ]


@app.post("/api/achievements/seed", response_model=SimpleResponse)
def seed_achievements(db: Session = Depends(get_db)):
    """
    POST /api/achievements/seed
    
    Seeds the database with predefined achievements.
    Only adds if table is empty.
    """
    existing = db.query(models.Achievement).count()
    if existing > 0:
        return {"message": f"Achievements already seeded ({existing} found). Skipping."}
    
    achievements = [
        {"key": "first_expense", "name": "Budget Beginner", "description": "Add your first expense", "xp_reward": 25, "icon_name": "ic_badge_expense"},
        {"key": "first_trade", "name": "Market Debut", "description": "Complete your first trade", "xp_reward": 50, "icon_name": "ic_badge_trade"},
        {"key": "week_streak", "name": "Week Warrior", "description": "Use app 7 days in a row", "xp_reward": 100, "icon_name": "ic_badge_streak"},
        {"key": "month_streak", "name": "Consistency King", "description": "Use app 30 days straight", "xp_reward": 500, "icon_name": "ic_badge_crown"},
        {"key": "budget_master", "name": "Budget Master", "description": "Stay under budget for 30 days", "xp_reward": 200, "icon_name": "ic_badge_budget"},
        {"key": "diversifier", "name": "Diversifier", "description": "Own 5 different stocks", "xp_reward": 75, "icon_name": "ic_badge_diversify"},
    ]
    
    for ach in achievements:
        db.add(models.Achievement(**ach))
    
    db.commit()
    return {"message": f"Successfully seeded {len(achievements)} achievements!"}


# =============================================================================
# LEADERBOARD API ENDPOINTS (Hall of Fame)
# =============================================================================

class LeaderboardEntry(BaseModel):
    """A single entry in the leaderboard with privacy-safe display name."""
    rank: int
    display_name: str  # Privacy-safe: "John D." not full name/email
    xp: int
    profile_picture: Optional[str] = None  # Base64 encoded image


class LeaderboardResponse(BaseModel):
    """Complete leaderboard response with top users and current user's rank."""
    top_users: List[LeaderboardEntry]
    user_rank: int
    user_xp: int
    user_display_name: str
    user_profile_picture: Optional[str] = None


def create_display_name(full_name: str) -> str:
    """
    Convert full name to privacy-safe display name.
    "Rahul Sharma" -> "Rahul S."
    "Alice" -> "Alice"
    """
    if not full_name or full_name.strip() == "":
        return "Anonymous"
    
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0]
    
    first_name = parts[0]
    last_initial = parts[-1][0].upper() + "."
    return f"{first_name} {last_initial}"


@app.get("/api/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(email: str = Query(...), db: Session = Depends(get_db)):
    """
    GET /api/leaderboard
    
    Returns the Top 50 users ranked by XP with privacy-safe display names,
    plus the requesting user's rank (even if outside Top 50).
    
    Query params:
    - email: The requesting user's email to calculate their rank
    """
    # Find current user
    current_user = db.query(models.User).filter(
        models.User.email == email.lower()
    ).first()
    
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # --- Query Top 50 users by XP (descending) ---
    top_users = db.query(models.User).order_by(
        models.User.xp.desc()
    ).limit(50).all()
    
    # Build leaderboard entries with privacy-safe names
    leaderboard_entries = []
    for rank, user in enumerate(top_users, start=1):
        leaderboard_entries.append(LeaderboardEntry(
            rank=rank,
            display_name=create_display_name(user.name),
            xp=user.xp or 0,
            profile_picture=user.profile_picture
        ))
    
    # --- Calculate current user's rank efficiently ---
    # Count how many users have MORE XP than current user
    users_above = db.query(models.User).filter(
        models.User.xp > (current_user.xp or 0)
    ).count()
    
    user_rank = users_above + 1
    
    return LeaderboardResponse(
        top_users=leaderboard_entries,
        user_rank=user_rank,
        user_xp=current_user.xp or 0,
        user_display_name=create_display_name(current_user.name),
        user_profile_picture=current_user.profile_picture
    )


# =============================================================================
# MARKET DATA ENDPOINTS (INDmoney-style)
# =============================================================================

class MarketIndex(BaseModel):
    """Schema for market index data."""
    name: str
    symbol: str
    value: float
    change: float
    change_percent: float
    is_positive: bool


class MarketIndicesResponse(BaseModel):
    """Response schema for market indices."""
    indices: List[MarketIndex]


@app.get("/api/market/indices", response_model=MarketIndicesResponse)
def get_market_indices():
    """
    GET /api/market/indices
    
    Returns current values of major Indian market indices:
    - NIFTY 50
    - SENSEX
    - BANK NIFTY
    """
    indices_symbols = [
        ("NIFTY 50", "^NSEI"),
        ("SENSEX", "^BSESN"),
        ("BANK NIFTY", "^NSEBANK"),
    ]
    
    result = []
    
    for name, symbol in indices_symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            
            if not hist.empty and len(hist) >= 1:
                current_value = float(hist['Close'].iloc[-1])
                prev_close = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else current_value
                change = current_value - prev_close
                change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
                
                result.append(MarketIndex(
                    name=name,
                    symbol=symbol,
                    value=round(current_value, 2),
                    change=round(change, 2),
                    change_percent=round(change_percent, 2),
                    is_positive=change >= 0
                ))
        except Exception as e:
            print(f"Error fetching {name}: {e}")
            # Add placeholder if fetch fails
            result.append(MarketIndex(
                name=name,
                symbol=symbol,
                value=0,
                change=0,
                change_percent=0,
                is_positive=True
            ))
    
    return MarketIndicesResponse(indices=result)


# --- Top Gainers/Losers ---

class StockItem(BaseModel):
    """Schema for stock item in lists."""
    symbol: str
    name: str
    sector: Optional[str] = None
    price: float
    change: float
    change_percent: float
    is_positive: bool
    logo_initial: str  # First letter for placeholder logo


class StockListResponse(BaseModel):
    """Response schema for stock lists."""
    stocks: List[StockItem]


# Popular Indian stocks for gainers/losers tracking
TRACKED_INDIAN_STOCKS = [
    ("RELIANCE.NS", "Reliance Industries", "Energy"),
    ("TCS.NS", "Tata Consultancy", "Technology"),
    ("INFY.NS", "Infosys", "Technology"),
    ("HDFCBANK.NS", "HDFC Bank", "Banking"),
    ("ICICIBANK.NS", "ICICI Bank", "Banking"),
    ("SBIN.NS", "State Bank of India", "Banking"),
    ("BHARTIARTL.NS", "Bharti Airtel", "Telecom"),
    ("ITC.NS", "ITC Limited", "Consumer"),
    ("KOTAKBANK.NS", "Kotak Mahindra", "Banking"),
    ("LT.NS", "Larsen & Toubro", "Infrastructure"),
    ("AXISBANK.NS", "Axis Bank", "Banking"),
    ("WIPRO.NS", "Wipro", "Technology"),
    ("HCLTECH.NS", "HCL Technologies", "Technology"),
    ("MARUTI.NS", "Maruti Suzuki", "Automobile"),
    ("TATAMOTORS.NS", "Tata Motors", "Automobile"),
    ("SUNPHARMA.NS", "Sun Pharma", "Pharma"),
    ("BAJFINANCE.NS", "Bajaj Finance", "Finance"),
    ("TITAN.NS", "Titan Company", "Consumer"),
    ("ADANIENT.NS", "Adani Enterprises", "Conglomerate"),
    ("POWERGRID.NS", "Power Grid", "Utilities"),
]


# Popular US stocks for the US Market section
TRACKED_US_STOCKS = [
    ("AAPL", "Apple Inc.", "Technology"),
    ("MSFT", "Microsoft", "Technology"),
    ("TSLA", "Tesla", "Automobile"),
    ("GOOGL", "Alphabet", "Technology"),
    ("AMZN", "Amazon", "Retail"),
    ("NVDA", "NVIDIA", "Semiconductors"),
    ("META", "Meta Platforms", "Technology"),
    ("NFLX", "Netflix", "Media"),
    ("AMD", "AMD", "Semiconductors"),
    ("DIS", "Walt Disney", "Media"),
    ("PYPL", "PayPal", "Fintech"),
    ("INTC", "Intel", "Semiconductors"),
    ("CRM", "Salesforce", "Technology"),
    ("ADBE", "Adobe", "Technology"),
    ("V", "Visa", "Fintech"),
]


def fetch_stock_data(stock_info):
    """Fetch stock data for a single stock."""
    symbol, name, sector = stock_info
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        
        if not hist.empty and len(hist) >= 1:
            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else current_price
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
            
            return StockItem(
                symbol=symbol.replace(".NS", ""),
                name=name,
                sector=sector,
                price=round(current_price, 2),
                change=round(change, 2),
                change_percent=round(change_percent, 2),
                is_positive=change >= 0,
                logo_initial=name[0].upper()
            )
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None


@app.get("/api/market/stocks", response_model=StockListResponse)
def get_all_stocks():
    """
    GET /api/market/stocks
    
    Returns list of popular Indian stocks with current prices.
    """
    stocks = []
    
    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_stock_data, TRACKED_INDIAN_STOCKS))
    
    stocks = [s for s in results if s is not None]
    
    # Sort by change percent (highest first for explore view)
    stocks.sort(key=lambda x: abs(x.change_percent), reverse=True)
    
    return StockListResponse(stocks=stocks)


@app.get("/api/market/top-gainers", response_model=StockListResponse)
def get_top_gainers():
    """
    GET /api/market/top-gainers
    
    Returns top 10 gaining stocks.
    """
    stocks = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_stock_data, TRACKED_INDIAN_STOCKS))
    
    stocks = [s for s in results if s is not None and s.is_positive]
    stocks.sort(key=lambda x: x.change_percent, reverse=True)
    
    return StockListResponse(stocks=stocks[:10])


@app.get("/api/market/top-losers", response_model=StockListResponse)
def get_top_losers():
    """
    GET /api/market/top-losers
    
    Returns top 10 losing stocks.
    """
    stocks = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_stock_data, TRACKED_INDIAN_STOCKS))
    
    stocks = [s for s in results if s is not None and not s.is_positive]
    stocks.sort(key=lambda x: x.change_percent)  # Most negative first
    
    return StockListResponse(stocks=stocks[:10])


# --- US STOCKS ENDPOINTS ---

def fetch_us_stock_data(stock_info):
    """
    Fetch stock data for a single US stock.
    Returns price in USD (no conversion to INR).
    """
    symbol, name, sector = stock_info
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        
        if not hist.empty and len(hist) >= 1:
            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else current_price
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
            
            return StockItem(
                symbol=symbol,  # Keep original symbol (no .NS suffix to strip)
                name=name,
                sector=sector,
                price=round(current_price, 2),  # Price in USD
                change=round(change, 2),
                change_percent=round(change_percent, 2),
                is_positive=change >= 0,
                logo_initial=name[0].upper()
            )
    except Exception as e:
        print(f"Error fetching US stock {symbol}: {e}")
    return None


@app.get("/api/market/stocks/us", response_model=StockListResponse)
def get_us_stocks():
    """
    GET /api/market/stocks/us
    
    Returns list of popular US stocks with current prices in USD.
    Prices are NOT converted to INR - display with $ symbol on frontend.
    """
    stocks = []
    
    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_us_stock_data, TRACKED_US_STOCKS))
    
    stocks = [s for s in results if s is not None]
    
    # Sort by change percent (highest first for explore view)
    stocks.sort(key=lambda x: abs(x.change_percent), reverse=True)
    
    return StockListResponse(stocks=stocks)


@app.get("/api/market/stocks/in", response_model=StockListResponse)
def get_indian_stocks():
    """
    GET /api/market/stocks/in
    
    Returns list of popular Indian stocks with current prices in INR.
    Alias endpoint for /api/market/stocks.
    """
    stocks = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_stock_data, TRACKED_INDIAN_STOCKS))
    
    stocks = [s for s in results if s is not None]
    stocks.sort(key=lambda x: abs(x.change_percent), reverse=True)
    
    return StockListResponse(stocks=stocks)


# =============================================================================
# CRYPTO ENDPOINTS
# =============================================================================

TRACKED_CRYPTOS = [
    ("BTC-USD", "Bitcoin", "BTC"),
    ("ETH-USD", "Ethereum", "ETH"),
    ("SOL-USD", "Solana", "SOL"),
    ("XRP-USD", "XRP", "XRP"),
    ("DOGE-USD", "Dogecoin", "DOGE"),
    ("ADA-USD", "Cardano", "ADA"),
    ("AVAX-USD", "Avalanche", "AVAX"),
    ("DOT-USD", "Polkadot", "DOT"),
    ("MATIC-USD", "Polygon", "MATIC"),
    ("LINK-USD", "Chainlink", "LINK"),
    ("SHIB-USD", "Shiba Inu", "SHIB"),
    ("LTC-USD", "Litecoin", "LTC"),
]


class CryptoItem(BaseModel):
    """Schema for crypto item."""
    symbol: str
    name: str
    short_name: str
    price_usd: float
    price_inr: float
    change_24h: float
    change_percent_24h: float
    is_positive: bool
    logo_initial: str


class CryptoListResponse(BaseModel):
    """Response schema for crypto list."""
    cryptos: List[CryptoItem]
    usd_to_inr: float


def fetch_crypto_data(crypto_info, usd_to_inr: float):
    """Fetch data for a single crypto."""
    symbol, name, short_name = crypto_info
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        
        if not hist.empty and len(hist) >= 1:
            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else current_price
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
            
            return CryptoItem(
                symbol=symbol,
                name=name,
                short_name=short_name,
                price_usd=round(current_price, 2),
                price_inr=round(current_price * usd_to_inr, 2),
                change_24h=round(change, 2),
                change_percent_24h=round(change_percent, 2),
                is_positive=change >= 0,
                logo_initial=short_name[0].upper()
            )
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None


@app.get("/api/crypto/list", response_model=CryptoListResponse)
def get_crypto_list():
    """
    GET /api/crypto/list
    
    Returns list of popular cryptocurrencies with prices in USD and INR.
    """
    # Get USD to INR rate
    usd_to_inr = 83.5  # Default fallback
    try:
        fx_ticker = yf.Ticker("USDINR=X")
        fx_hist = fx_ticker.history(period="1d")
        if not fx_hist.empty:
            usd_to_inr = float(fx_hist['Close'].iloc[-1])
    except:
        pass
    
    cryptos = []
    
    # Fetch crypto data with exchange rate
    def fetch_with_rate(crypto_info):
        return fetch_crypto_data(crypto_info, usd_to_inr)
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(fetch_with_rate, TRACKED_CRYPTOS))
    
    cryptos = [c for c in results if c is not None]
    
    return CryptoListResponse(cryptos=cryptos, usd_to_inr=round(usd_to_inr, 2))


@app.get("/api/crypto/top-gainers", response_model=CryptoListResponse)
def get_crypto_gainers():
    """
    GET /api/crypto/top-gainers
    
    Returns top gaining cryptos.
    """
    usd_to_inr = 83.5
    try:
        fx_ticker = yf.Ticker("USDINR=X")
        fx_hist = fx_ticker.history(period="1d")
        if not fx_hist.empty:
            usd_to_inr = float(fx_hist['Close'].iloc[-1])
    except:
        pass
    
    def fetch_with_rate(crypto_info):
        return fetch_crypto_data(crypto_info, usd_to_inr)
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(fetch_with_rate, TRACKED_CRYPTOS))
    
    cryptos = [c for c in results if c is not None and c.is_positive]
    cryptos.sort(key=lambda x: x.change_percent_24h, reverse=True)
    
    return CryptoListResponse(cryptos=cryptos, usd_to_inr=round(usd_to_inr, 2))
