import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.sentiment_helper import detect_sentiment, get_sentiment_badge

def test_sentiment_rules():
    print("--- Running Sentiment Detection Tests ---")
    
    # 1. Happy/Positive texts
    happy_texts = [
        "This is a great service, thank you!",
        "Awesome customer support, very helpful.",
        "Perfect response, I am very pleased."
    ]
    for text in happy_texts:
        res = detect_sentiment(text)
        print(f"Text: '{text}' -> Sentiment: {res}")
        assert res == "Happy"
        
    # 2. Frustrated/Negative texts
    frustrated_texts = [
        "I am so frustrated with this slow policy renewal delay.",
        "Worst customer experience ever, terribly disappointed.",
        "This system is useless, I hate the delays."
    ]
    for text in frustrated_texts:
        res = detect_sentiment(text)
        print(f"Text: '{text}' -> Sentiment: {res}")
        assert res == "Frustrated"
        
    # 3. Neutral texts
    neutral_texts = [
        "What is the renewal due date for Easy Health?",
        "Please let me know the premium amount.",
        "I want to check my active policy list."
    ]
    for text in neutral_texts:
        res = detect_sentiment(text)
        print(f"Text: '{text}' -> Sentiment: {res}")
        assert res == "Neutral"
        
    print("\nAll sentiment detection verification tests completed successfully!")

if __name__ == "__main__":
    test_sentiment_rules()
