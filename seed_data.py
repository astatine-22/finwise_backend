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
    print("Checking and seeding professional finance course content...")

    videos_data = [
        # --- MODULE 1: BASICS ---
        {
            "title": "Stock Market for Beginners",
            "description": "Complete guide to understanding the stock market basics.",
            "youtube_video_id": "3UQDtJXX0z0",
            "category": "Module 1: Basics",
            "duration_minutes": 15,
            "is_featured": True,
            "order_index": 1
        },
        {
            "title": "What is Sensex & Nifty?",
            "description": "Understanding the major Indian stock market indices.",
            "youtube_video_id": "81bd99F6H8A",
            "category": "Module 1: Basics",
            "duration_minutes": 12,
            "is_featured": False,
            "order_index": 2
        },
        {
            "title": "What is a Demat Account?",
            "description": "Why you need a Demat account and how to open one.",
            "youtube_video_id": "fJ9w9aY5m0c",
            "category": "Module 1: Basics",
            "duration_minutes": 10,
            "is_featured": False,
            "order_index": 3
        },
        {
            "title": "How to Buy First Share",
            "description": "Step-by-step guide to buying your first stock in India.",
            "youtube_video_id": "Xn7Kk9sP0LM",
            "category": "Module 1: Basics",
            "duration_minutes": 14,
            "is_featured": True,
            "order_index": 4
        },

        # --- MODULE 2: MUTUAL FUNDS ---
        {
            "title": "Mutual Funds Explained",
            "description": "What are mutual funds and how do they work?",
            "youtube_video_id": "tRC5aQ7sMhQ",
            "category": "Module 2: Mutual Funds",
            "duration_minutes": 15,
            "is_featured": True,
            "order_index": 5
        },
        {
            "title": "SIP vs Lumpsum",
            "description": "Which investment strategy is better for you?",
            "youtube_video_id": "Uz2eJ6fWqkE",
            "category": "Module 2: Mutual Funds",
            "duration_minutes": 10,
            "is_featured": False,
            "order_index": 6
        },
        {
            "title": "Power of Compounding",
            "description": "How compound interest makes you rich over time.",
            "youtube_video_id": "g-7pM_y9j5s",
            "category": "Module 2: Mutual Funds",
            "duration_minutes": 8,
            "is_featured": False,
            "order_index": 7
        },
        {
            "title": "Best Mutual Funds",
            "description": "How to select the best mutual funds for your portfolio.",
            "youtube_video_id": "Q7_fF2J9_nE",
            "category": "Module 2: Mutual Funds",
            "duration_minutes": 12,
            "is_featured": False,
            "order_index": 8
        },

        # --- MODULE 3: PERSONAL FINANCE ---
        {
            "title": "50/30/20 Rule",
            "description": "The golden rule of budgeting explained.",
            "youtube_video_id": "s3EtjSg_bF4",
            "category": "Module 3: Personal Finance",
            "duration_minutes": 10,
            "is_featured": True,
            "order_index": 9
        },
        {
            "title": "Emergency Fund Guide",
            "description": "Why and how to build an emergency fund.",
            "youtube_video_id": "9L9I_K2kFkI",
            "category": "Module 3: Personal Finance",
            "duration_minutes": 8,
            "is_featured": False,
            "order_index": 10
        },
        {
            "title": "Credit Cards 101",
            "description": "How to use credit cards wisely and build credit score.",
            "youtube_video_id": "4j2emMn7UaI",
            "category": "Module 3: Personal Finance",
            "duration_minutes": 12,
            "is_featured": False,
            "order_index": 11
        },
        {
            "title": "Income Tax Basics",
            "description": "Understanding income tax slabs and planning.",
            "youtube_video_id": "b8_9j6kHh9I",
            "category": "Module 3: Personal Finance",
            "duration_minutes": 15,
            "is_featured": True,
            "order_index": 12
        }
    ]

    count = 0
    for video_data in videos_data:
        # Check if video exists by ID
        existing_video = db.query(models.LearnVideo).filter_by(youtube_video_id=video_data["youtube_video_id"]).first()
        
        if not existing_video:
            # Generate thumbnail URL
            video_data["thumbnail_url"] = f"https://img.youtube.com/vi/{video_data['youtube_video_id']}/hqdefault.jpg"
            
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
                
            count += 1
            print(f"Added video: {video.title}")
        else:
            print(f"Skipping duplicate video: {video_data['title']}")
    
    db.commit()
    print(f"✅ Successfully seeded {count} new professional course videos AND Quizzes!")


def reset_and_seed(db):
    """
    HARD RESET: Deletes all Learn/Quiz data and reseeds with verified content.
    Now uses Full YouTube URLs for easier data entry.
    """
    print("⚠️  STARTING HARD RESET OF LEARN CONTENT...")
    
    # 1. Delete in order of Safe Referential Integrity (Child -> Parent)
    deleted_q = db.query(models.QuizQuestion).delete()
    deleted_quiz = db.query(models.Quiz).delete()
    deleted_v = db.query(models.LearnVideo).delete()
    
    db.commit()
    print(f"🗑️  Deleted {deleted_q} questions, {deleted_quiz} quizzes, {deleted_v} videos.")

    # 2. Reseed with VERIFIED Full URLs
    verified_videos = [
        # --- MODULE 1: STOCK MARKET BASICS ---
        {"title": "How the Stock Market Works", "url": "https://www.youtube.com/watch?v=p7HKvqRI_Bo", "cat": "Module 1: Stock Market Basics", "dur": 15},
        {"title": "What is the Stock Market?", "url": "https://www.youtube.com/watch?v=ZCFkWDdmXG8", "cat": "Module 1: Stock Market Basics", "dur": 12},
        {"title": "Buying Your First Stock", "url": "https://www.youtube.com/watch?v=bTvx6c2Yy1k", "cat": "Module 1: Stock Market Basics", "dur": 14},
        {"title": "Investing for Beginners", "url": "https://www.youtube.com/watch?v=i5qUq7E-PUQ", "cat": "Module 1: Stock Market Basics", "dur": 18},
        
        # --- MODULE 2: MUTUAL FUNDS ---
        {"title": "Mutual Funds Explained", "url": "https://www.youtube.com/watch?v=tRC5aQ7sMhQ", "cat": "Module 2: Mutual Funds", "dur": 15},
        {"title": "SIP vs Lumpsum", "url": "https://www.youtube.com/watch?v=ImZz4R5p_6c", "cat": "Module 2: Mutual Funds", "dur": 10},
        {"title": "Power of Compounding", "url": "https://www.youtube.com/watch?v=6mIbI17p_kU", "cat": "Module 2: Mutual Funds", "dur": 8},
        {"title": "Index Funds vs Mutual Funds", "url": "https://www.youtube.com/watch?v=H9eIgnC60b0", "cat": "Module 2: Mutual Funds", "dur": 13},

        # --- MODULE 3: PERSONAL FINANCE ---
        {"title": "50/30/20 Budget Rule", "url": "https://www.youtube.com/watch?v=s3EtjSg_bF4", "cat": "Module 3: Personal Finance", "dur": 10},
        {"title": "Emergency Fund Guide", "url": "https://www.youtube.com/watch?v=9L9I_K2kFkI", "cat": "Module 3: Personal Finance", "dur": 8},
        {"title": "Credit Cards 101", "url": "https://www.youtube.com/watch?v=4j2emMn7UaI", "cat": "Module 3: Personal Finance", "dur": 12},
        {"title": "Income Tax Basics", "url": "https://www.youtube.com/watch?v=b8_9j6kHh9I", "cat": "Module 3: Personal Finance", "dur": 15},

        # --- MODULE 4: CRYPTOCURRENCY ---
        {"title": "Bitcoin for Beginners", "url": "https://www.youtube.com/watch?v=s4g1XFU8Gto", "cat": "Module 4: Cryptocurrency", "dur": 12},
        {"title": "What is Blockchain?", "url": "https://www.youtube.com/watch?v=SSo_EIwHSd4", "cat": "Module 4: Cryptocurrency", "dur": 14},
        {"title": "Crypto vs Stocks", "url": "https://www.youtube.com/watch?v=1YyAzVmP9xM", "cat": "Module 4: Cryptocurrency", "dur": 10},
        {"title": "How to Buy Crypto Safe", "url": "https://www.youtube.com/watch?v=LcJPd5wJ7Zk", "cat": "Module 4: Cryptocurrency", "dur": 16},
    ]

    count = 0
    for v_data in verified_videos:
        # Extract video ID from URL for thumbnail generation
        video_id = v_data["url"].split("v=")[1].split("&")[0] if "v=" in v_data["url"] else ""
        
        video = models.LearnVideo(
            title=v_data["title"],
            description=f"Learn about {v_data['title']}",
            thumbnail_url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            youtube_video_id=v_data["url"],  # Store full URL here
            category=v_data["cat"],
            duration_minutes=v_data["dur"],
            is_featured=True,
            order_index=count + 1
        )
        db.add(video)
        db.flush()

        # Add Quiz
        quiz = models.Quiz(title=f"Quiz: {video.title}", video_id=video.id)
        db.add(quiz)
        db.flush()

        # Add generic questions
        questions = [
            models.QuizQuestion(quiz_id=quiz.id, question_text=f"What is the main topic of {video.title}?", option_a="Finance", option_b="Art", option_c="Music", option_d="Dance", correct_option="A", xp_value=10),
            models.QuizQuestion(quiz_id=quiz.id, question_text="Which strategy helps build wealth?", option_a="Consistent investing", option_b="Gambling", option_c="Hoarding cash", option_d="Avoiding markets", correct_option="A", xp_value=10),
            models.QuizQuestion(quiz_id=quiz.id, question_text="What is the benefit of starting early?", option_a="Compound growth", option_b="Higher taxes", option_c="More debt", option_d="Less savings", correct_option="A", xp_value=10),
            models.QuizQuestion(quiz_id=quiz.id, question_text="What should you prioritize?", option_a="Emergency fund", option_b="Luxury purchases", option_c="Risky bets", option_d="Ignoring budgets", correct_option="A", xp_value=10),
            models.QuizQuestion(quiz_id=quiz.id, question_text="How much XP for this quiz?", option_a="50 XP", option_b="0 XP", option_c="5 XP", option_d="1 XP", correct_option="A", xp_value=10),
        ]
        for q in questions:
            db.add(q)
        
        count += 1
    
    db.commit()
    print(f"✅ HARD RESET COMPLETE. Seeded {count} videos with full URLs.")


if __name__ == "__main__":
    main()
