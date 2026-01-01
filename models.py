from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Text, Date
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    xp = Column(Integer, default=0)
    has_completed_onboarding = Column(Boolean, default=False)
    profile_picture = Column(Text, nullable=True)  # Base64 encoded image
    budget_limit = Column(Float, default=20000.0, nullable=False)  # User's monthly budget limit in ₹
    
    # Gamification: Streak tracking
    last_activity_date = Column(Date, nullable=True)  # Last day user was active
    current_streak = Column(Integer, default=0)        # Consecutive days of activity
    
    # Relationships
    portfolio = relationship("Portfolio", back_populates="user", uselist=False)
    achievements = relationship("UserAchievement", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    # We use user_id to link to the User table securely
    user_id = Column(Integer, ForeignKey("users.id"))  
    title = Column(String)
    amount = Column(Float)       # Float allows cents (e.g. 12.50)
    category = Column(String)
    date = Column(DateTime)      # Real time object for sorting


# ============================================================================
# LEARN MODULE - Educational Video Content
# ============================================================================

class LearnVideo(Base):
    """
    Stores educational video metadata for the Learn section.
    Videos are sourced from YouTube and categorized by topic.
    """
    __tablename__ = "learn_videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    youtube_video_id = Column(String, nullable=False)  # e.g., "dQw4w9WgXcQ"
    category = Column(String, nullable=False)  # e.g., "Investing Basics", "Crypto", "Budgeting"
    duration_minutes = Column(Integer, nullable=True)
    is_featured = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)  # For custom ordering


# ============================================================================
# PAPER TRADING MODELS
# ============================================================================

class Portfolio(Base):
    """
    Represents a user's virtual paper trading portfolio.
    One-to-one relationship with User.
    Stores the available virtual cash balance in Indian Rupees (₹).
    """
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Virtual cash balance - starts at ₹1,00,000 (1 Lakh Rupees)
    virtual_cash = Column(Float, default=100000.0, nullable=False)
    
    # Timestamp for when the portfolio was created
    created_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="portfolio")
    holdings = relationship("Holding", back_populates="portfolio", cascade="all, delete-orphan")


class Holding(Base):
    """
    Represents an individual asset holding within a portfolio.
    Many-to-one relationship with Portfolio (a portfolio can have multiple holdings).
    Tracks the asset symbol, quantity owned, and average purchase price in Rupees.
    """
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    
    # Asset details
    asset_symbol = Column(String, nullable=False)  # e.g., "RELIANCE.NS", "TCS.NS", "BTC-INR"
    quantity = Column(Float, nullable=False)        # Number of shares/units owned
    average_buy_price = Column(Float, nullable=False)  # Weighted average purchase price in ₹
    
    # Relationship back to portfolio
    portfolio = relationship("Portfolio", back_populates="holdings")


# ============================================================================
# GAMIFICATION MODELS - Achievements & Badges
# ============================================================================

class Achievement(Base):
    """
    Defines available achievements/badges that users can earn.
    Each achievement has an XP reward and icon reference for frontend display.
    """
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)   # Unique identifier e.g., "first_trade"
    name = Column(String, nullable=False)               # Display name e.g., "Market Debut"
    description = Column(String, nullable=False)        # What user did to earn it
    xp_reward = Column(Integer, default=50)             # XP awarded when earned
    icon_name = Column(String, nullable=False)          # Frontend drawable reference
    
    # Relationship to earned instances
    user_achievements = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    """
    Links users to their earned achievements.
    Many-to-many relationship between User and Achievement.
    """
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    earned_at = Column(DateTime, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")


# ============================================================================
# TRANSACTION LEDGER - Trade History
# ============================================================================

class Transaction(Base):
    """
    Records all buy/sell transactions for audit trail and history.
    All monetary values are stored in Indian Rupees (₹).
    Tracks currency conversion for US stocks and brokerage fees.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Trade details
    symbol = Column(String, nullable=False)           # e.g., "RELIANCE.NS", "AAPL", "BTC-INR"
    type = Column(String, nullable=False)             # "BUY" or "SELL"
    quantity = Column(Float, nullable=False)
    
    # Pricing (all in ₹)
    price_per_share = Column(Float, nullable=False)   # In ₹ (converted if USD stock)
    total_amount = Column(Float, nullable=False)      # price_per_share * quantity (in ₹)
    brokerage_fee = Column(Float, nullable=False)     # 0.1% fee in ₹
    
    # Timestamp
    timestamp = Column(DateTime, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="transactions")