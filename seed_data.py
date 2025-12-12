"""
FinWise Database Seed Script
Run this script once to populate the learn_videos table with initial data.

Usage:
    cd finWise_backend
    python seed_data.py
"""

from database import SessionLocal, engine
import models

# Create tables if they don't exist
models.Base.metadata.create_all(bind=engine)


def seed_learn_videos(db):
    """Seed the learn_videos table with financial education videos."""
    
    # Check if videos already exist
    existing_count = db.query(models.LearnVideo).count()
    if existing_count > 0:
        print(f"Learn videos already seeded ({existing_count} videos found). Skipping...")
        return
    
    videos = [
        # Investing Basics Category
        models.LearnVideo(
            title="Stock Market for Beginners",
            description="Learn the basics of how the stock market works, including stocks, exchanges, and how to start investing.",
            thumbnail_url="https://img.youtube.com/vi/p7HKvqRI_Bo/maxresdefault.jpg",
            youtube_video_id="p7HKvqRI_Bo",
            category="Investing Basics",
            duration_minutes=15,
            is_featured=True,
            order_index=1
        ),
        models.LearnVideo(
            title="What are Mutual Funds?",
            description="Understand mutual funds, how they work, and why they're a great option for beginner investors in India.",
            thumbnail_url="https://img.youtube.com/vi/ngfKXvfzC74/maxresdefault.jpg",
            youtube_video_id="ngfKXvfzC74",
            category="Investing Basics",
            duration_minutes=12,
            is_featured=True,
            order_index=2
        ),
        models.LearnVideo(
            title="SIP vs Lump Sum Investment",
            description="Learn the difference between Systematic Investment Plans and lump sum investing. Which is better for you?",
            thumbnail_url="https://img.youtube.com/vi/3NcJpLVMCjI/maxresdefault.jpg",
            youtube_video_id="3NcJpLVMCjI",
            category="Investing Basics",
            duration_minutes=10,
            is_featured=False,
            order_index=3
        ),
        
        # Budgeting Category
        models.LearnVideo(
            title="50/30/20 Budgeting Rule Explained",
            description="Master the popular 50/30/20 rule for budgeting. Allocate your income for needs, wants, and savings effectively.",
            thumbnail_url="https://img.youtube.com/vi/HQzoZfc3GwQ/maxresdefault.jpg",
            youtube_video_id="HQzoZfc3GwQ",
            category="Budgeting",
            duration_minutes=8,
            is_featured=True,
            order_index=4
        ),
        models.LearnVideo(
            title="How to Save Money Fast",
            description="Practical tips and tricks to save money quickly without sacrificing your lifestyle completely.",
            thumbnail_url="https://img.youtube.com/vi/fv_tN3Ov1Nw/maxresdefault.jpg",
            youtube_video_id="fv_tN3Ov1Nw",
            category="Budgeting",
            duration_minutes=11,
            is_featured=False,
            order_index=5
        ),
        
        # Cryptocurrency Category
        models.LearnVideo(
            title="Bitcoin Explained Simply",
            description="What is Bitcoin? How does it work? A simple explanation of the world's first cryptocurrency.",
            thumbnail_url="https://img.youtube.com/vi/41JCpzvnn_0/maxresdefault.jpg",
            youtube_video_id="41JCpzvnn_0",
            category="Crypto",
            duration_minutes=9,
            is_featured=True,
            order_index=6
        ),
        models.LearnVideo(
            title="Blockchain Technology Explained",
            description="Understand the technology behind cryptocurrencies - blockchain. Learn how it works and why it matters.",
            thumbnail_url="https://img.youtube.com/vi/SSo_EIwHSd4/maxresdefault.jpg",
            youtube_video_id="SSo_EIwHSd4",
            category="Crypto",
            duration_minutes=14,
            is_featured=False,
            order_index=7
        ),
        
        # Personal Finance Category
        models.LearnVideo(
            title="Emergency Fund: Why You Need One",
            description="Learn why an emergency fund is crucial and how much you should save for unexpected expenses.",
            thumbnail_url="https://img.youtube.com/vi/fVToMS2Q3XQ/maxresdefault.jpg",
            youtube_video_id="fVToMS2Q3XQ",
            category="Personal Finance",
            duration_minutes=7,
            is_featured=False,
            order_index=8
        ),
    ]
    
    # Add all videos to database
    for video in videos:
        db.add(video)
    
    db.commit()
    print(f"Successfully seeded {len(videos)} learn videos!")


def main():
    print("=" * 50)
    print("FinWise Database Seeding Script")
    print("=" * 50)
    
    db = SessionLocal()
    
    try:
        seed_learn_videos(db)
        print("\nDatabase seeding completed successfully!")
    except Exception as e:
        print(f"\nError during seeding: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
