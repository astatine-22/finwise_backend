"""
Seed script for populating the learn_videos table with educational content.
Run this script to initialize the Learn section with curated financial education videos.

Usage:
    python seed_learn_videos.py [--clear]
    
Options:
    --clear: Clear existing video data before seeding
"""

from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, LearnVideo
import sys

# Video data extracted from YouTube thumbnails
VIDEO_DATA = [
    {
        "title": "How the Stock Market Works",
        "description": "Oliver Elfenbaum explains the history of the Dutch East India Company and how modern stock markets function today. \n\nKEY LEARNINGS:\n• The history of the first stock market.\n• What 'Shares' actually represent.\n• Why companies go public (IPOs).",
        "youtube_video_id": "p7HKvqRI_Bo",  # Extracted from thumbnail URL
        "thumbnail_url": "https://img.youtube.com/vi/p7HKvqRI_Bo/maxresdefault.jpg",
        "category": "Investing Basics",
        "duration_minutes": 5,
        "is_featured": True,
        "order_index": 1
    },
    {
        "title": "What is the Stock Market?",
        "description": "A clear and simple explanation of what the stock market actually is and how it connects buyers and sellers. \n\nKEY LEARNINGS:\n• The concept of a stock exchange.\n• How supply and demand affect prices.\n• The role of a broker.",
        "youtube_video_id": "ZCFkWDdmXG8",
        "thumbnail_url": "https://img.youtube.com/vi/ZCFkWDdmXG8/maxresdefault.jpg",
        "category": "Investing Basics",
        "duration_minutes": 4,
        "is_featured": False,
        "order_index": 2
    },
    {
        "title": "Buying Your First Stock",
        "description": "A step-by-step guide on how to actually purchase your first stock using a brokerage app. \n\nKEY LEARNINGS:\n• How to open a Demat account.\n• Placing a market order vs. limit order.\n• Understanding ticker symbols.",
        "youtube_video_id": "bb6_M_srMBk",
        "thumbnail_url": "https://img.youtube.com/vi/bb6_M_srMBk/maxresdefault.jpg",
        "category": "Investing Basics",
        "duration_minutes": 6,
        "is_featured": False,
        "order_index": 3
    },
    {
        "title": "Investing for Beginners",
        "description": "The ultimate guide to starting your investment journey, covering the mindset and basic strategies you need. \n\nKEY LEARNINGS:\n• The difference between saving and investing.\n• Risk vs. Reward.\n• Long-term thinking.",
        "youtube_video_id": "lNdOtlpmH5U",
        "thumbnail_url": "https://img.youtube.com/vi/lNdOtlpmH5U/maxresdefault.jpg",
        "category": "Investing Basics",
        "duration_minutes": 8,
        "is_featured": True,
        "order_index": 4
    },
    {
        "title": "Mutual Funds Explained",
        "description": "What are mutual funds and why are they safer than individual stocks? This video breaks it down. \n\nKEY LEARNINGS:\n• How a fund manager handles your money.\n• Diversification benefits.\n• Types of funds (Equity, Debt, Hybrid).",
        "youtube_video_id": "JUtes-k-VX4",
        "thumbnail_url": "https://img.youtube.com/vi/JUtes-k-VX4/maxresdefault.jpg",
        "category": "Mutual Funds",
        "duration_minutes": 5,
        "is_featured": False,
        "order_index": 5
    },
    {
        "title": "SIP vs Lumpsum",
        "description": "Should you invest all at once or little by little? We compare Systematic Investment Plans (SIP) with Lumpsum investing. \n\nKEY LEARNINGS:\n• Benefits of Rupee Cost Averaging.\n• Why SIP is better for beginners.\n• When to use Lumpsum.",
        "youtube_video_id": "KIsY08zUrOU",
        "thumbnail_url": "https://img.youtube.com/vi/KIsY08zUrOU/maxresdefault.jpg",
        "category": "Mutual Funds",
        "duration_minutes": 4,
        "is_featured": False,
        "order_index": 6
    },
    {
        "title": "Power of Compounding",
        "description": "Einstein called it the 8th wonder of the world. See how small investments grow into massive wealth over time. \n\nKEY LEARNINGS:\n• The math behind compound interest.\n• Starting early vs. starting late.\n• The exponential growth curve.",
        "youtube_video_id": "NuhVK4r-VQw",
        "thumbnail_url": "https://img.youtube.com/vi/NuhVK4r-VQw/maxresdefault.jpg",
        "category": "Wealth Building",
        "duration_minutes": 5,
        "is_featured": True,
        "order_index": 7
    },
    {
        "title": "Index Funds vs Mutual Funds",
        "description": "Active vs Passive investing. Why do many experts recommend low-cost Index Funds? \n\nKEY LEARNINGS:\n• What is an Index Fund (Nifty 50).\n• Expense ratios and fees.\n• Active management risks.",
        "youtube_video_id": "DUL6cLZfmEM",
        "thumbnail_url": "https://img.youtube.com/vi/DUL6cLZfmEM/maxresdefault.jpg",
        "category": "Mutual Funds",
        "duration_minutes": 6,
        "is_featured": False,
        "order_index": 8
    },
    {
        "title": "50/30/20 Budget Rule",
        "description": "The simplest budgeting rule to manage your salary effectively without stress. \n\nKEY LEARNINGS:\n• 50% for Needs (Rent, Food).\n• 30% for Wants (Entertainment).\n• 20% for Savings & Investments.",
        "youtube_video_id": "XLD0f5Nzr3c",
        "thumbnail_url": "https://img.youtube.com/vi/XLD0f5Nzr3c/maxresdefault.jpg",
        "category": "Personal Finance",
        "duration_minutes": 4,
        "is_featured": False,
        "order_index": 9
    },
    {
        "title": "Emergency Fund Guide",
        "description": "Before you invest, you need a safety net. Learn how much cash you should keep for emergencies. \n\nKEY LEARNINGS:\n• Why you need 6 months of expenses.\n• Where to park this money (Liquid Funds).\n• Avoiding debt during crises.",
        "youtube_video_id": "R2OvsQCubGw",
        "thumbnail_url": "https://img.youtube.com/vi/R2OvsQCubGw/maxresdefault.jpg",
        "category": "Personal Finance",
        "duration_minutes": 5,
        "is_featured": False,
        "order_index": 10
    },
    {
        "title": "Income Tax Basics (80C, TDS)",
        "description": "Tax season doesn't have to be scary. Learn the basics of saving tax in India. \n\nKEY LEARNINGS:\n• Section 80C deductions (PPF, ELSS).\n• What is TDS?\n• Old Regime vs New Regime.",
        "youtube_video_id": "iTUv3GlFsds",
        "thumbnail_url": "https://img.youtube.com/vi/iTUv3GlFsds/maxresdefault.jpg",
        "category": "Taxation",
        "duration_minutes": 7,
        "is_featured": False,
        "order_index": 11
    },
    {
        "title": "Bitcoin for Beginners",
        "description": "A beginner-friendly introduction to the world's first cryptocurrency. \n\nKEY LEARNINGS:\n• What is Bitcoin?\n• Decentralization explained.\n• Digital Gold concept.",
        "youtube_video_id": "s4g1XFU8Gto",
        "thumbnail_url": "https://img.youtube.com/vi/s4g1XFU8Gto/maxresdefault.jpg",
        "category": "Crypto",
        "duration_minutes": 6,
        "is_featured": False,
        "order_index": 12
    },
    {
        "title": "What is Blockchain?",
        "description": "The technology behind crypto. Understand how the blockchain ledger actually works. \n\nKEY LEARNINGS:\n• How blocks are chained together.\n• Why it is immutable and secure.\n• Use cases beyond money.",
        "youtube_video_id": "SSo_EIwHSd4",
        "thumbnail_url": "https://img.youtube.com/vi/SSo_EIwHSd4/maxresdefault.jpg",
        "category": "Crypto",
        "duration_minutes": 5,
        "is_featured": False,
        "order_index": 13
    },
    {
        "title": "Crypto vs Stocks",
        "description": "Comparing the two biggest asset classes. Which one is right for you? \n\nKEY LEARNINGS:\n• Volatility differences.\n• Ownership rights.\n• Market hours (24/7 vs 9-3).",
        "youtube_video_id": "HEWgveRCsQ4",
        "thumbnail_url": "https://img.youtube.com/vi/HEWgveRCsQ4/maxresdefault.jpg",
        "category": "Crypto",
        "duration_minutes": 5,
        "is_featured": False,
        "order_index": 14
    },
    {
        "title": "How to Buy Crypto Safe",
        "description": "Safety first! How to buy cryptocurrency without getting scammed or hacked. \n\nKEY LEARNINGS:\n• Choosing a safe exchange.\n• Hot wallets vs Cold wallets.\n• Spotting phishing scams.",
        "youtube_video_id": "tXMtUT5MNQw",
        "thumbnail_url": "https://img.youtube.com/vi/tXMtUT5MNQw/maxresdefault.jpg",
        "category": "Crypto",
        "duration_minutes": 6,
        "is_featured": False,
        "order_index": 15
    }
]


def seed_videos(db: Session, clear_existing: bool = False):
    """
    Seed the learn_videos table with educational content.
    
    Args:
        db: Database session
        clear_existing: If True, delete all existing videos before seeding
    """
    try:
        if clear_existing:
            print("🗑️  Clearing existing video data...")
            db.query(LearnVideo).delete()
            db.commit()
            print("✅ Existing data cleared")
        
        print(f"\n📹 Seeding {len(VIDEO_DATA)} educational videos...")
        
        for idx, video_data in enumerate(VIDEO_DATA, 1):
            video = LearnVideo(**video_data)
            db.add(video)
            print(f"   [{idx}/{len(VIDEO_DATA)}] Added: {video_data['title']}")
        
        db.commit()
        print(f"\n✅ Successfully seeded {len(VIDEO_DATA)} videos!")
        
        # Print summary by category
        print("\n📊 Videos by Category:")
        categories = {}
        for video in VIDEO_DATA:
            cat = video['category']
            categories[cat] = categories.get(cat, 0) + 1
        
        for category, count in sorted(categories.items()):
            print(f"   • {category}: {count} videos")
        
        featured_count = sum(1 for v in VIDEO_DATA if v['is_featured'])
        print(f"\n⭐ Featured videos: {featured_count}")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error seeding videos: {e}")
        raise


def main():
    """Main entry point for the seeding script."""
    clear_existing = "--clear" in sys.argv
    
    print("=" * 60)
    print("🎓 FinWise Learn Video Seeding Script")
    print("=" * 60)
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Create database session
    db = SessionLocal()
    
    try:
        seed_videos(db, clear_existing=clear_existing)
    finally:
        db.close()
    
    print("\n" + "=" * 60)
    print("✨ Seeding complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
