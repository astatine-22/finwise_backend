from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
import yfinance as yf

# --- SECURITY IMPORTS ---
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets

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
# SECURITY CONFIGURATION
# =============================================================================

# JWT Configuration
# IMPORTANT: In production, use a secure secret key from environment variables
SECRET_KEY = "your-super-secret-key-change-in-production-finwise-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password Hashing Configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# --- CONFIGURATION ---
# REPLACE WITH YOUR ACTUAL BACKEND CLIENT ID FROM GOOGLE CLOUD CONSOLE
GOOGLE_CLIENT_ID = "783108831764-djrpp609l2rj7kch5imn32d5rb474qf7.apps.googleusercontent.com"


# =============================================================================
# SECURITY HELPER FUNCTIONS
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


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
    user: Optional[UserProfile] = None


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

# 1. SIGNUP (with bcrypt password hashing)
@app.post("/api/auth/signup", response_model=TokenResponse)
def signup(user: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user with bcrypt password hashing."""
    db_user = db.query(models.User).filter(models.User.email == user.email.lower()).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password before storing
    hashed_password = get_password_hash(user.password)
    
    new_user = models.User(
        name=user.name,
        email=user.email.lower(),
        password=hashed_password,  # Store bcrypt hash, not plaintext
        xp=100
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create and return JWT token
    access_token = create_access_token(data={"sub": new_user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"name": new_user.name, "xp": new_user.xp, "profile_picture": new_user.profile_picture}
    }

# 2. NORMAL LOGIN (with bcrypt verification and JWT token)
@app.post("/api/auth/login", response_model=TokenResponse)
def login(user: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with bcrypt password verification and return JWT."""
    db_user = db.query(models.User).filter(models.User.email == user.email.lower()).first()
    
    # Check if user exists
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    # Check if this is a Google-only account (empty password)
    if db_user.password == "":
        raise HTTPException(status_code=400, detail="Please login with Google")
    
    # Verify password using bcrypt
    if not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    # Create and return JWT token
    access_token = create_access_token(data={"sub": db_user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"name": db_user.name, "xp": db_user.xp, "profile_picture": db_user.profile_picture}
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


# --- BUDGET & EXPENSE ROUTES ---

# 5. ADD EXPENSE (UPDATED to accept optional date)
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

# 7. GET BUDGET SUMMARY (With Range Filter)
@app.get("/api/budget/summary/{email}", response_model=BudgetSummaryResponse)
def get_budget_summary(email: str, range: str = Query("1m"), db: Session = Depends(get_db)):
    # Hardcoded limit for now. In the future, this could be dynamic based on range.
    budget_limit = 20000.0 

    user = db.query(models.User).filter(models.User.email == email.lower()).first()
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
    executed_price: float
    total_cost: float
    remaining_cash: float
    new_holding_quantity: float
    new_average_price: float


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


# --- Paper Trading API Endpoints ---

@app.get("/api/trade/portfolio", response_model=PortfolioSummaryResponse)
def get_portfolio_summary(email: str = Query(...), db: Session = Depends(get_db)):
    """
    GET /api/trade/portfolio
    
    Fetches the user's complete portfolio summary including:
    - Virtual cash balance
    - All holdings with real-time valuations
    - Total portfolio value (cash + holdings)
    - Profit/loss calculations for each holding
    
    If the user doesn't have a portfolio, one is created with $10,000.
    """
    # Find user by email
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get or create portfolio
    portfolio = get_or_create_portfolio(user, db)
    
    # Build holdings response with real-time prices
    holdings_response: List[HoldingResponse] = []
    total_holdings_value = 0.0
    
    for holding in portfolio.holdings:
        # Fetch current market price
        current_price = get_current_price(holding.asset_symbol)
        
        if current_price is not None:
            current_value = current_price * holding.quantity
            cost_basis = holding.average_buy_price * holding.quantity
            profit_loss = current_value - cost_basis
            profit_loss_percent = ((current_price - holding.average_buy_price) / holding.average_buy_price) * 100
            total_holdings_value += current_value
        else:
            # If price fetch fails, use average buy price as fallback
            current_value = holding.average_buy_price * holding.quantity
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
    
    Executes a buy order for the specified asset:
    1. Fetches current real-time price via yfinance
    2. Validates user has sufficient virtual cash
    3. Deducts cost from portfolio cash
    4. Updates existing holding (with weighted average price) or creates new one
    5. Returns execution confirmation
    
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
    
    # --- Step 1: Fetch current market price ---
    current_price = get_current_price(symbol)
    
    if current_price is None:
        raise HTTPException(
            status_code=400, 
            detail=f"Unable to fetch price for symbol '{symbol}'. Please verify the symbol is valid (e.g., 'RELIANCE.NS' for Reliance, 'TCS.NS' for TCS, 'BTC-INR' for Bitcoin in INR)."
        )
    
    if current_price <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid price received for symbol '{symbol}'. Please try again."
        )
    
    # --- Step 2: Calculate total cost and validate funds ---
    total_cost = current_price * quantity
    
    if total_cost > portfolio.virtual_cash:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Required: ₹{total_cost:,.2f}, Available: ₹{portfolio.virtual_cash:,.2f}"
        )
    
    # --- Step 3: Execute the trade (transactional) ---
    try:
        # Deduct cash from portfolio
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
            new_value = quantity * current_price
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
                average_buy_price=current_price
            )
            db.add(new_holding)
            
            final_quantity = quantity
            final_avg_price = current_price
        
        # Commit the transaction
        db.commit()
        
        return TradeExecutionResponse(
            message=f"Successfully purchased {quantity} units of {symbol}",
            asset_symbol=symbol,
            quantity=quantity,
            executed_price=round(current_price, 2),
            total_cost=round(total_cost, 2),
            remaining_cash=round(portfolio.virtual_cash, 2),
            new_holding_quantity=round(final_quantity, 4),
            new_average_price=round(final_avg_price, 2)
        )
        
    except Exception as e:
        # Rollback on any error to maintain data integrity
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Trade execution failed: {str(e)}"
        )


# --- Additional Utility Endpoint: Get Asset Price ---

class AssetPriceResponse(BaseModel):
    """Response schema for asset price lookup."""
    symbol: str
    current_price: Optional[float]
    currency: str = "USD"
    source: str = "Yahoo Finance"


@app.get("/api/trade/price/{symbol}", response_model=AssetPriceResponse)
def get_asset_price(symbol: str):
    """
    GET /api/trade/price/{symbol}
    
    Utility endpoint to look up the current price of any asset.
    Useful for the frontend to display prices before placing an order.
    """
    normalized_symbol = symbol.upper().strip()
    price = get_current_price(normalized_symbol)
    
    if price is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find price for symbol '{normalized_symbol}'. Please verify the symbol is valid."
        )
    
    return AssetPriceResponse(
        symbol=normalized_symbol,
        current_price=round(price, 2)
    )


# --- Price History Endpoint (for charts) ---

class PricePoint(BaseModel):
    """Single price point for charting."""
    timestamp: int  # Unix timestamp in milliseconds
    price: float

class PriceHistoryResponse(BaseModel):
    """Response schema for price history data."""
    symbol: str
    period: str
    data: List[PricePoint]
    price_change: float
    price_change_percent: float
    current_price: float
    previous_close: float


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
    """
    try:
        normalized_symbol = symbol.upper().strip()
        ticker = yf.Ticker(normalized_symbol)
        
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
        
        # Convert to list of price points
        data_points = []
        for index, row in hist.iterrows():
            timestamp_ms = int(index.timestamp() * 1000)
            data_points.append(PricePoint(
                timestamp=timestamp_ms,
                price=round(float(row['Close']), 2)
            ))
        
        # Calculate price change
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
        
        return PriceHistoryResponse(
            symbol=normalized_symbol,
            period=period,
            data=data_points,
            price_change=round(price_change, 2),
            price_change_percent=round(price_change_percent, 2),
            current_price=round(current_price, 2),
            previous_close=round(first_price, 2)
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