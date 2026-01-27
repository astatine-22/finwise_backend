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
    HARD RESET: Deletes all Learn/Quiz data and reseeds with verified content.
    Now uses Full YouTube URLs for easier data entry.
    Now uses REAL Quiz Questions mapped to specific videos.
    """
    print("⚠️  STARTING HARD RESET OF LEARN CONTENT...")
    
    # 1. Delete in order of Safe Referential Integrity (Child -> Parent)
    deleted_q = db.query(models.QuizQuestion).delete()
    deleted_quiz = db.query(models.Quiz).delete()
    deleted_v = db.query(models.LearnVideo).delete()
    
    db.commit()
    print(f"🗑️  Deleted {deleted_q} questions, {deleted_quiz} quizzes, {deleted_v} videos.")

    # 2. Define Real Quiz Questions Dictionary
    quiz_data = {
        # === MODULE 1: STOCK MARKET BASICS ===
        "How the Stock Market Works": [
            {"q": "What does IPO stand for?", "a": "Initial Public Offering", "b": "Indian Public Office", "c": "Internal Profit Order", "d": "Initial Private Owner", "correct": "A"},
            {"q": "What do you actually own when you buy a share?", "a": "A digital token", "b": "A partial ownership in the company", "c": "A debt paper", "d": "Nothing, it's just gambling", "correct": "B"},
            {"q": "Which is a major Stock Exchange in India?", "a": "NYSE", "b": "NSE", "c": "FOREX", "d": "NASDAQ", "correct": "B"},
            {"q": "Who regulates the Stock Market in India?", "a": "RBI", "b": "SEBI", "c": "SBI", "d": "Government of India", "correct": "B"},
            {"q": "What is a 'Bull Market'?", "a": "When prices are falling", "b": "When prices are rising", "c": "When the market is closed", "d": "A market for selling cattle", "correct": "B"}
        ],
        "What is the Stock Market?": [
            {"q": "The stock market is primarily a place to...", "a": "Buy groceries", "b": "Buy and sell securities", "c": "Exchange currency", "d": "Take loans", "correct": "B"},
            {"q": "What drives stock prices in the short term?", "a": "Company earnings", "b": "Supply and Demand", "c": "The weather", "d": "Fixed government rates", "correct": "B"},
            {"q": "Can you lose money in the stock market?", "a": "No, it's guaranteed profit", "b": "Yes, if the stock price drops", "c": "Only if the broker runs away", "d": "No, SEBI protects you", "correct": "B"},
            {"q": "What is a 'Dividend'?", "a": "A tax you pay", "b": "A fee to the broker", "c": "A share of profits paid to shareholders", "d": "A loan", "correct": "C"},
            {"q": "Why do companies sell stock?", "a": "To raise capital for growth", "b": "To become famous", "c": "To avoid paying taxes", "d": "To pay off the government", "correct": "A"}
        ],
        "Buying Your First Stock": [
            {"q": "What account is needed to hold shares electronically?", "a": "Savings Account", "b": "Demat Account", "c": "Current Account", "d": "Fixed Deposit", "correct": "B"},
            {"q": "Who executes your buy/sell orders?", "a": "The Bank", "b": "The Stock Broker", "c": "The Company CEO", "d": "The Government", "correct": "B"},
            {"q": "What is a 'Market Order'?", "a": "Buying at current price", "b": "Buying at a specific price", "c": "Buying after market closes", "d": "Buying vegetables", "correct": "A"},
            {"q": "What should you check before buying?", "a": "Logo color", "b": "Company fundamentals", "c": "Friend's advice", "d": "If it is cheap", "correct": "B"},
            {"q": "What is 'Diversification'?", "a": "Buying one stock", "b": "Buying stocks in different industries", "c": "Selling quickly", "d": "Buying only Tech stocks", "correct": "B"}
        ],
        "Investing for Beginners": [
            {"q": "What is key to successful investing?", "a": "Timing the market", "b": "Time in the market (Long term)", "c": "Day trading", "d": "Rumors", "correct": "B"},
            {"q": "Which asset class has highest risk?", "a": "Bonds", "b": "Fixed Deposits", "c": "Stocks/Equities", "d": "Gold", "correct": "C"},
            {"q": "What is 'Inflation'?", "a": "Rising prices decreasing money's value", "b": "Stock prices going up", "c": "Getting a bonus", "d": "A tax", "correct": "A"},
            {"q": "Why start investing early?", "a": "To look cool", "b": "To benefit from Compounding", "c": "To pay taxes", "d": "Because brokers say so", "correct": "B"},
            {"q": "What is a 'Blue Chip' stock?", "a": "Cheap stock", "b": "Stock of a large, reliable company", "c": "Tech stock", "d": "Gambling stock", "correct": "B"}
        ],
        # === MODULE 2: MUTUAL FUNDS ===
        "Mutual Funds Explained": [
            {"q": "What is a Mutual Fund?", "a": "A bank loan", "b": "Pool of money managed by professionals", "c": "Government scheme", "d": "Insurance", "correct": "B"},
            {"q": "Who manages a Mutual Fund?", "a": "Investors", "b": "Fund Manager", "c": "SEBI", "d": "Bank Manager", "correct": "B"},
            {"q": "What is NAV?", "a": "Net Asset Value", "b": "New Account Verification", "c": "Net Average Velocity", "d": "No Asset Value", "correct": "A"},
            {"q": "Are Mutual Funds risk-free?", "a": "Yes", "b": "No, subject to market risks", "c": "Only debt funds", "d": "Yes, if held for 1 year", "correct": "B"},
            {"q": "What is an 'Exit Load'?", "a": "Entry fee", "b": "Fee for redeeming early", "c": "Tax", "d": "Management fee", "correct": "B"}
        ],
        "SIP vs Lumpsum": [
            {"q": "What does SIP stand for?", "a": "Systematic Investment Plan", "b": "Secure Investment Process", "c": "Simple Interest Payment", "d": "Stock Index Price", "correct": "A"},
            {"q": "What is 'Rupee Cost Averaging'?", "a": "Buying more units when prices are low", "b": "Averaging bank balance", "c": "Calculating taxes", "d": "Buying when market is high", "correct": "A"},
            {"q": "When is Lumpsum suggested?", "a": "Market all-time high", "b": "When markets are low/corrected", "c": "Every month", "d": "Never", "correct": "B"},
            {"q": "Can you stop a SIP anytime?", "a": "No, locked for 5 years", "b": "Yes, usually without penalty", "c": "Only with court order", "d": "No", "correct": "B"},
            {"q": "Which is better for salaried people?", "a": "Lumpsum", "b": "SIP", "c": "Trading", "d": "Real Estate", "correct": "B"}
        ],
        "Power of Compounding": [
            {"q": "Einstein called Compounding the...", "a": "Eighth wonder of the world", "b": "Root of all evil", "c": "Biggest scam", "d": "Best math trick", "correct": "A"},
            {"q": "What is required for compounding?", "a": "High Risk", "b": "Time", "c": "Luck", "d": "Large Capital", "correct": "B"},
            {"q": "10k doubled every year for 3 years is?", "a": "30k", "b": "40k", "c": "80k", "d": "60k", "correct": "C"},
            {"q": "Does delaying investment affect returns?", "a": "No", "b": "Yes, significantly reduces them", "c": "Slightly", "d": "Increases returns", "correct": "B"},
            {"q": "Compounding applies to...", "a": "Only Stocks", "b": "Only FDs", "c": "Any investment where earnings are reinvested", "d": "Only Gold", "correct": "C"}
        ],
        "Index Funds vs Mutual Funds": [
            {"q": "What is an Index Fund?", "a": "Fund mimicking a market index", "b": "Fund managed by robot", "c": "High risk fund", "d": "Government bond", "correct": "A"},
            {"q": "Which has lower fees?", "a": "Active Funds", "b": "Index Funds", "c": "Same", "d": "Hedge Funds", "correct": "B"},
            {"q": "Goal of an Active Fund?", "a": "Match market", "b": "Beat the market", "c": "Lose money", "d": "Track index", "correct": "B"},
            {"q": "Who recommends Index Funds?", "a": "Elon Musk", "b": "Warren Buffett", "c": "Bill Gates", "d": "Jeff Bezos", "correct": "B"},
            {"q": "Index funds are...", "a": "Passive Investing", "b": "Active Investing", "c": "Gambling", "d": "Day Trading", "correct": "A"}
        ],
        # === MODULE 3: PERSONAL FINANCE ===
        "50/30/20 Budget Rule": [
            {"q": "In 50/30/20, what is 50% for?", "a": "Wants", "b": "Needs", "c": "Savings", "d": "Charity", "correct": "B"},
            {"q": "What is the 20% for?", "a": "Fun", "b": "Savings & Investments", "c": "Shopping", "d": "Rent", "correct": "B"},
            {"q": "Is Netflix a Need or Want?", "a": "Need", "b": "Want", "c": "Savings", "d": "None", "correct": "B"},
            {"q": "Why budget?", "a": "To stop spending", "b": "To track and control money", "c": "To impress banks", "d": "Not important", "correct": "B"},
            {"q": "If you earn 100k, save at least?", "a": "50k", "b": "20k", "c": "30k", "d": "10k", "correct": "B"}
        ],
        "Emergency Fund Guide": [
            {"q": "What is an Emergency Fund?", "a": "Vacation money", "b": "Phone money", "c": "Cash for unexpected shocks", "d": "Retirement fund", "correct": "C"},
            {"q": "How many months expenses?", "a": "1 month", "b": "3 to 6 months", "c": "1 year", "d": "2 weeks", "correct": "B"},
            {"q": "Where to keep it?", "a": "Stocks", "b": "Liquid Assets (Savings/Liquid Funds)", "c": "Real Estate", "d": "Locked FD", "correct": "B"},
            {"q": "Is a new iPhone an emergency?", "a": "Yes", "b": "No", "c": "If old one breaks", "d": "If on sale", "correct": "B"},
            {"q": "When to start building?", "a": "After retiring", "b": "Before investing", "c": "After buying house", "d": "Never", "correct": "B"}
        ],
        "Credit Cards 101": [
            {"q": "What is a Credit Score?", "a": "Bank balance", "b": "Measure of creditworthiness", "c": "Shopping points", "d": "Card count", "correct": "B"},
            {"q": "What if you pay only 'Minimum Due'?", "a": "Nothing", "b": "You pay huge interest", "c": "Bank rewards you", "d": "Limit increases", "correct": "B"},
            {"q": "Is a Credit Card bad?", "a": "Yes", "b": "No, if used responsibly", "c": "It's a scam", "d": "Free money", "correct": "B"},
            {"q": "What is 'Interest Free Period'?", "a": "Time before bill payment", "b": "Time to ignore bank", "c": "Free loan time", "d": "Forever", "correct": "A"},
            {"q": "Does 100% utilization help score?", "a": "Yes", "b": "No, hurts score", "c": "No effect", "d": "Shows wealth", "correct": "B"}
        ],
        "Income Tax Basics": [
            {"q": "What is Section 80C?", "a": "Penalty", "b": "Tax deduction for investments", "c": "Salary income", "d": "GST rule", "correct": "B"},
            {"q": "Max limit for 80C?", "a": "50k", "b": "1.5 Lakhs", "c": "5 Lakhs", "d": "Unlimited", "correct": "B"},
            {"q": "Which saves tax under 80C?", "a": "5-year FD", "b": "Savings Interest", "c": "Gold", "d": "Car Loan", "correct": "A"},
            {"q": "What is TDS?", "a": "Tax Deducted at Source", "b": "Total Deposit Scheme", "c": "Tax Direct System", "d": "Time Deposit", "correct": "A"},
            {"q": "Is ELSS tax-saving?", "a": "No", "b": "Yes", "c": "Only for seniors", "d": "Illegal", "correct": "B"}
        ],
        # === MODULE 4: CRYPTOCURRENCY ===
        "Bitcoin for Beginners": [
            {"q": "Who created Bitcoin?", "a": "Elon Musk", "b": "Satoshi Nakamoto", "c": "Bill Gates", "d": "Vitalik Buterin", "correct": "B"},
            {"q": "Bitcoin is decentralized. Meaning?", "a": "No value", "b": "No central authority", "c": "Illegal", "d": "Controlled by Google", "correct": "B"},
            {"q": "Max supply of Bitcoin?", "a": "Unlimited", "b": "21 Million", "c": "100 Million", "d": "1 Billion", "correct": "B"},
            {"q": "Where are Bitcoins stored?", "a": "Bank", "b": "Digital Wallet", "c": "Pocket", "d": "Paper", "correct": "B"},
            {"q": "Is Bitcoin physical?", "a": "Yes", "b": "No, digital code", "c": "Gold plated", "d": "Copper", "correct": "B"}
        ],
        "What is Blockchain?": [
            {"q": "What is a Blockchain?", "a": "Chain", "b": "Distributed digital ledger", "c": "Bank software", "d": "Social site", "correct": "B"},
            {"q": "What makes it secure?", "a": "Passwords", "b": "Cryptography & immutability", "c": "Police", "d": "Not secure", "correct": "B"},
            {"q": "Can you delete a transaction?", "a": "Yes", "b": "No, it is immutable", "c": "On Sundays", "d": "If you pay", "correct": "B"},
            {"q": "Who owns public Blockchain?", "a": "Microsoft", "b": "No one / Participants", "c": "Government", "d": "Bank", "correct": "B"},
            {"q": "What is a 'Miner'?", "a": "Gold digger", "b": "Computer validating transactions", "c": "Hacker", "d": "Banker", "correct": "B"}
        ],
        "Crypto vs Stocks": [
            {"q": "Which market is open 24/7?", "a": "Stock", "b": "Crypto", "c": "Bond", "d": "Gold", "correct": "B"},
            {"q": "Which is more volatile?", "a": "Stocks", "b": "Crypto", "c": "Real Estate", "d": "FDs", "correct": "B"},
            {"q": "Do you own company equity in Crypto?", "a": "Yes", "b": "No", "c": "Sometimes", "d": "With Bitcoin", "correct": "B"},
            {"q": "Which is regulated by SEBI?", "a": "Crypto", "b": "Stocks", "c": "Both", "d": "Neither", "correct": "B"},
            {"q": "Can you buy fractions?", "a": "No", "b": "Yes (e.g. 0.001)", "c": "0.5 only", "d": "No", "correct": "B"}
        ],
        "How to Buy Crypto Safe": [
            {"q": "What is a 'Private Key'?", "a": "Access password (Keep safe)", "b": "Public address", "c": "Safe key", "d": "Username", "correct": "A"},
            {"q": "Safest storage for large amounts?", "a": "Exchange", "b": "Hardware Wallet (Cold)", "c": "Phone", "d": "Wall", "correct": "B"},
            {"q": "What is 'Phishing'?", "a": "Fishing", "b": "Scams stealing login/keys", "c": "Buying", "d": "Selling", "correct": "B"},
            {"q": "Invest emergency fund in Crypto?", "a": "Yes", "b": "No, too risky", "c": "Maybe", "d": "Always", "correct": "B"},
            {"q": "What is 'DYOR'?", "a": "Do Your Own Research", "b": "Risk", "c": "Returns", "d": "Yield", "correct": "A"}
        ]
    }

    # 3. Reseed with VERIFIED Full URLs
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

        # Add REAL questions from quiz_data dictionary
        if video.title in quiz_data:
            question_list = quiz_data[video.title]
            for q_data in question_list:
                question = models.QuizQuestion(
                    quiz_id=quiz.id,
                    question_text=q_data["q"],
                    option_a=q_data["a"],
                    option_b=q_data["b"],
                    option_c=q_data["c"],
                    option_d=q_data["d"],
                    correct_option=q_data["correct"],
                    xp_value=10
                )
                db.add(question)
        else:
            # Fallback generic questions if video not in dictionary
            print(f"⚠️ No quiz data for '{video.title}', using generic questions")
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
    print(f"✅ HARD RESET COMPLETE. Seeded {count} videos with REAL quiz questions.")


def main():
    """Main function to run the database seeding."""
    db = SessionLocal()
    try:
        reset_and_seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
