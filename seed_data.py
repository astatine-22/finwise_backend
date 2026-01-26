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


def seed_professional_course(db):
    """
    Seed valid professional finance course data.
    Structure: 3 Modules x 4 Videos = 12 Videos.
    """
    # Check if videos already exist
    existing_videos = db.query(models.LearnVideo).all()
    
    if existing_videos:
        print(f"Found {len(existing_videos)} existing videos. Checking for missing quizzes...")
        quiz_count = 0
        for video in existing_videos:
            # Check if likely a professional course video (has title Module...) or just any video
            # We will add quiz to ALL videos for now to be safe
            
            existing_quiz = db.query(models.Quiz).filter_by(video_id=video.id).first()
            if not existing_quiz:
                 # Create Quiz for this video
                quiz = models.Quiz(
                    title=f"Quiz: {video.title}",
                    video_id=video.id
                )
                db.add(quiz)
                db.flush()

                # Create 5 Questions
                questions = [
                    models.QuizQuestion(
                        quiz_id=quiz.id,
                        question_text=f"What is the main topic of {video.title}?",
                        option_a="Finance",
                        option_b="Cooking",
                        option_c="Sports",
                        option_d="Music",
                        correct_option="A",
                        xp_value=10
                    ),
                    models.QuizQuestion(
                        quiz_id=quiz.id,
                        question_text="Concept Check: True or False?",
                        option_a="True",
                        option_b="False",
                        option_c="Maybe",
                        option_d="Unknown",
                        correct_option="A",
                        xp_value=10
                    ),
                    models.QuizQuestion(
                        quiz_id=quiz.id,
                        question_text="Select the correct statement:",
                        option_a="Investing grows wealth",
                        option_b="Saving is useless",
                        option_c="Debt is good",
                        option_d="Spend everything",
                        correct_option="A",
                        xp_value=10
                    ),
                     models.QuizQuestion(
                        quiz_id=quiz.id,
                        question_text="Key takeaway from this lesson?",
                        option_a="Start early",
                        option_b="Wait for luck",
                        option_c="Avoid money",
                        option_d="None of the above",
                        correct_option="A",
                        xp_value=10
                    ),
                     models.QuizQuestion(
                        quiz_id=quiz.id,
                        question_text="How much XP is this worth?",
                        option_a="10 XP",
                        option_b="0 XP",
                        option_c="100 XP",
                        option_d="50 XP",
                        correct_option="A",
                        xp_value=10
                    )
                ]
                for q in questions:
                    db.add(q)
                quiz_count += 1
        
        if quiz_count > 0:
            db.commit()
            print(f"✅ Retroactively seeded {quiz_count} missing quizzes for existing videos!")
        else:
            print("All videos already have quizzes.")
        return

    print("Seeding professional finance course content...")

    videos_data = [
        # --- MODULE 1: STOCK MARKET BASICS ---
        {
            "title": "Module 1: How the Stock Market Works",
            "description": "A comprehensive introduction to the stock market, exchanges (NSE/BSE), and how shares are traded.",
            "thumbnail_url": "https://img.youtube.com/vi/p7HKvqRI_Bo/hqdefault.jpg",
            "youtube_video_id": "p7HKvqRI_Bo",
            "category": "Stock Market Basics",
            "duration_minutes": 15,
            "is_featured": True,
            "order_index": 1
        },
        {
            "title": "Module 1: Bull vs Bear Markets Explained",
            "description": "Understand market cycles. What defines a Bull market versus a Bear market and how to invest in each.",
            "thumbnail_url": "https://img.youtube.com/vi/gvZSpET11ZY/hqdefault.jpg",
            "youtube_video_id": "gvZSpET11ZY",
            "category": "Stock Market Basics",
            "duration_minutes": 12,
            "is_featured": False,
            "order_index": 2
        },
        {
            "title": "Module 1: Market Capitalization Types",
            "description": "Large-cap, Mid-cap, and Small-cap stocks explained. Learn the risk and reward profile of each category.",
            "thumbnail_url": "https://img.youtube.com/vi/b11Vrdw_3uU/hqdefault.jpg",
            "youtube_video_id": "b11Vrdw_3uU",
            "category": "Stock Market Basics",
            "duration_minutes": 10,
            "is_featured": False,
            "order_index": 3
        },
        {
            "title": "Module 1: Fundamental vs Technical Analysis",
            "description": "The difference between analyzing company fundamentals vs reading chart patterns for trading.",
            "thumbnail_url": "https://img.youtube.com/vi/Xn7KWR9EOGQ/hqdefault.jpg",
            "youtube_video_id": "Xn7KWR9EOGQ",
            "category": "Stock Market Basics",
            "duration_minutes": 18,
            "is_featured": True,
            "order_index": 4
        },

        # --- MODULE 2: MUTUAL FUNDS & SIPs ---
        {
            "title": "Module 2: Mutual Funds for Beginners",
            "description": "What are Mutual Funds? How they pool money from investors to buy a basket of securities.",
            "thumbnail_url": "https://img.youtube.com/vi/UZgRHNvOXFk/hqdefault.jpg",
            "youtube_video_id": "UZgRHNvOXFk",
            "category": "Mutual Funds & SIPs",
            "duration_minutes": 14,
            "is_featured": True,
            "order_index": 5
        },
        {
            "title": "Module 2: Power of Compounding (SIP)",
            "description": "See the magic of compound interest with Systematic Investment Plans (SIP) over the long term.",
            "thumbnail_url": "https://img.youtube.com/vi/Xr3lBXPWw30/hqdefault.jpg",
            "youtube_video_id": "Xr3lBXPWw30",
            "category": "Mutual Funds & SIPs",
            "duration_minutes": 11,
            "is_featured": False,
            "order_index": 6
        },
        {
            "title": "Module 2: Active vs Passive Funds",
            "description": "Should you pay for a fund manager or buy the index? Analyzing expense ratios and performance.",
            "thumbnail_url": "https://img.youtube.com/vi/fvGLnthJDsg/hqdefault.jpg",
            "youtube_video_id": "fvGLnthJDsg",
            "category": "Mutual Funds & SIPs",
            "duration_minutes": 16,
            "is_featured": False,
            "order_index": 7
        },
        {
            "title": "Module 2: How to Choose a Mutual Fund",
            "description": "A checklist for selecting the right mutual fund based on your goals, risk tolerance, and time horizon.",
            "thumbnail_url": "https://img.youtube.com/vi/RkyXOH6laXA/hqdefault.jpg",
            "youtube_video_id": "RkyXOH6laXA",
            "category": "Mutual Funds & SIPs",
            "duration_minutes": 13,
            "is_featured": False,
            "order_index": 8
        },

        # --- MODULE 3: TAX & FINANCIAL PLANNING ---
        {
            "title": "Module 3: Income Tax Basics (Old vs New)",
            "description": "Understanding the Indian Income Tax slabs and the difference between the Old and New tax regimes.",
            "thumbnail_url": "https://img.youtube.com/vi/BjpGmqo7z1A/hqdefault.jpg",
            "youtube_video_id": "BjpGmqo7z1A",
            "category": "Tax & Financial Planning",
            "duration_minutes": 20,
            "is_featured": True,
            "order_index": 9
        },
        {
            "title": "Module 3: Tax Saving via Section 80C",
            "description": "How to save tax legally using PPF, ELSS, EPF, and other instruments under Section 80C.",
            "thumbnail_url": "https://img.youtube.com/vi/1BYs84vegLk/hqdefault.jpg",
            "youtube_video_id": "1BYs84vegLk",
            "category": "Tax & Financial Planning",
            "duration_minutes": 15,
            "is_featured": False,
            "order_index": 10
        },
        {
            "title": "Module 3: Why You Need Health Insurance",
            "description": "Financial planning isn't just about investing; it's about protection. Importance of health and term insurance.",
            "thumbnail_url": "https://img.youtube.com/vi/uB_YqwqK_hE/hqdefault.jpg",
            "youtube_video_id": "uB_YqwqK_hE",
            "category": "Tax & Financial Planning",
            "duration_minutes": 12,
            "is_featured": False,
            "order_index": 11
        },
        {
            "title": "Module 3: Retirement Planning 101",
            "description": "How to calculate your retirement corpus and start planning for your golden years early.",
            "thumbnail_url": "https://img.youtube.com/vi/Gj3sQhD_M-4/hqdefault.jpg",
            "youtube_video_id": "Gj3sQhD_M-4",
            "category": "Tax & Financial Planning",
            "duration_minutes": 14,
            "is_featured": True,
            "order_index": 12
        }
    ]

    count = 0
    for video_data in videos_data:
        video = models.LearnVideo(**video_data)
        db.add(video)
        db.flush() # Flush to get video.id

        # Create a Quiz for this video
        quiz = models.Quiz(
            title=f"Quiz: {video.title}",
            video_id=video.id
        )
        db.add(quiz)
        db.flush() # Flush to get quiz.id

        # Create 5 Questions for this quiz
        questions = [
            models.QuizQuestion(
                quiz_id=quiz.id,
                question_text=f"What is the main topic of {video.title}?",
                option_a="Finance",
                option_b="Cooking",
                option_c="Sports",
                option_d="Music",
                correct_option="A",
                xp_value=10
            ),
            models.QuizQuestion(
                quiz_id=quiz.id,
                question_text="Which concept was discussed?",
                option_a="Key Financial Concept",
                option_b="Irrelevant Detail",
                option_c="Wrong Fact",
                option_d="Another Wrong Fact",
                correct_option="A",
                xp_value=10
            ),
            models.QuizQuestion(
                quiz_id=quiz.id,
                question_text="True or False: This is important for investors.",
                option_a="True",
                option_b="False",
                option_c="Maybe",
                option_d="Unknown",
                correct_option="A",
                xp_value=10
            ),
             models.QuizQuestion(
                quiz_id=quiz.id,
                question_text="What is the best approach mentioned?",
                option_a="Long-term consistency",
                option_b="Gambling",
                option_c="Ignoring data",
                option_d="Panic selling",
                correct_option="A",
                xp_value=10
            ),
             models.QuizQuestion(
                quiz_id=quiz.id,
                question_text="How does this help your portfolio?",
                option_a="Reduces risk / Increases growth",
                option_b="Guarantees loss",
                option_c="No impact",
                option_d="Increases fees only",
                correct_option="A",
                xp_value=10
            )
        ]
        
        for q in questions:
            db.add(q)
            
        count += 1
    
    db.commit()
    print(f"✅ Successfully seeded {count} professional course videos AND Quizzes!")


def main():
    print("=" * 50)
    print("FinWise Database Seeding Script")
    print("=" * 50)
    
    db = SessionLocal()
    
    try:
        # Using the new professional course seeder
        seed_professional_course(db)
        print("\nDatabase seeding completed successfully!")
    except Exception as e:
        print(f"\nError during seeding: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
