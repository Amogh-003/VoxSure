import re

def detect_sentiment(text: str) -> str:
    """
    Classifies a given text string into one of three sentiment categories:
    Happy, Frustrated, or Neutral.
    """
    if not text:
        return "Neutral"
        
    text_lower = text.lower().strip()
    
    # Negative/Frustrated keywords
    frustrated_keywords = [
        "frustrated", "angry", "bad", "terrible", "worst", "hate", "useless", "slow", 
        "delay", "nonsense", "annoyed", "dissatisfied", "disappointed", "complaint", 
        "issue", "problem", "broken", "crap", "fail", "annoying", "poor", "unhappy", 
        "waste", "stupid", "idiot"
    ]
    
    # Positive/Happy keywords
    happy_keywords = [
        "great", "awesome", "excellent", "happy", "thank", "thanks", "perfect", "good", 
        "nice", "love", "wonderful", "satisfying", "helpful", "amazing", "superb", "glad", 
        "pleased", "fantastic", "cool", "fine"
    ]
    
    # Check for matches
    has_frustrated = any(re.search(rf"\b{word}\b", text_lower) for word in frustrated_keywords)
    has_happy = any(re.search(rf"\b{word}\b", text_lower) for word in happy_keywords)
    
    if has_frustrated:
        return "Frustrated"
    elif has_happy:
        return "Happy"
    else:
        return "Neutral"

def get_sentiment_badge(sentiment: str) -> str:
    """
    Returns a formatted HTML/CSS badge string for Streamlit display.
    """
    if sentiment == "Happy":
        return '<span style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); padding: 4px 8px; border-radius: 12px; font-weight: 600; font-size: 0.85em; display: inline-flex; align-items: center; gap: 4px; animation: pulse 2s infinite;">🟢 Happy</span>'
    elif sentiment == "Frustrated":
        return '<span style="background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 8px; border-radius: 12px; font-weight: 600; font-size: 0.85em; display: inline-flex; align-items: center; gap: 4px; animation: pulse 2s infinite;">🔴 Frustrated</span>'
    else:
        return '<span style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); padding: 4px 8px; border-radius: 12px; font-weight: 600; font-size: 0.85em; display: inline-flex; align-items: center; gap: 4px;">🟡 Neutral</span>'
