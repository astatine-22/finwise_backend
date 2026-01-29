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


def reset_and_seed(db):
    """
    HARD RESET: Deletes all Learn data and reseeds with verified content.
    Now uses Full YouTube URLs for easier data entry.
    """
    print("⚠️  STARTING HARD RESET OF LEARN CONTENT...")
    
    # 1. Delete in order
    deleted_v = db.query(models.LearnVideo).delete()
    
    db.commit()
    print(f"🗑️  Deleted {deleted_v} videos.")

    # 2. Reseed with Firebase Video URLs (ExoPlayer compatible)
    # NOTE: youtube_video_id field now stores direct MP4 URLs from Firebase Storage
    # NOTE: description contains "KEY LEARNINGS:" marker - Android app splits on this
    verified_videos = [
        {
            "title": "How does the stock market work?",
            "url": "https://firebasestorage.googleapis.com/v0/b/finwise-479119.firebasestorage.app/o/How%20does%20the%20stock%20market%20work_%20-%20Oliver%20Elfenbaum.mp4?alt=media&token=cc7ae80e-fb9b-4cca-b20c-ef955f136dd9",
            "cat": "Investing Basics",
            "dur": 5,
            "desc": """In this video, Oliver Elfenbaum explains the history of the Dutch East India Company and how modern stock markets function today. We explore the concepts of initial public offerings (IPOs) and how trading works.

KEY LEARNINGS:
• The history of the Dutch East India Company.
• What 'Shares' actually represent.
• Why companies go public (IPOs).
• How supply and demand drives stock prices."""
        },
    ]

    count = 0
    for v_data in verified_videos:
        # For Firebase URLs, we don't have auto-thumbnails like YouTube
        # Using a placeholder or you can add your own thumbnail_url field to v_data
        video = models.LearnVideo(
            title=v_data["title"],
            description=v_data.get("desc", f"Learn about {v_data['title']}"),
            thumbnail_url=v_data.get("thumbnail", ""),  # Empty or add custom thumbnail
            youtube_video_id=v_data["url"],  # This now stores Firebase MP4 URL
            category=v_data["cat"],
            duration_minutes=v_data["dur"],
            is_featured=True,
            order_index=count + 1
        )
        db.add(video)
        count += 1
    
    db.commit()
    print(f"✅ HARD RESET COMPLETE. Seeded {count} videos.")


def main():
    """Main function to run the database seeding."""
    db = SessionLocal()
    try:
        reset_and_seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
