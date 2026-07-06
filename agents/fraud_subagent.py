from google.adk.agents import Agent

def verify_fraud_risk_tool(policy_commencement: str, diagnosis: str, claimed_amount: float, sum_insured: float, last_claim_status: str) -> str:
    """
    Evaluates a claim for fraud risk based on policy guidelines and returns risk assessment.
    
    Args:
        policy_commencement: The policy commencement date (YYYY-MM-DD or DD/MM/YYYY).
        diagnosis: The diagnosed illness or reason for claim.
        claimed_amount: The billed claim amount.
        sum_insured: The policy's total sum insured limit.
        last_claim_status: The status of the customer's last claim.
        
    Returns:
        A risk evaluation assessment string.
    """
    import datetime
    
    # Parse commencement date
    try:
        comm_date = datetime.datetime.strptime(policy_commencement, "%Y-%m-%d").date()
    except Exception:
        try:
            comm_date = datetime.datetime.strptime(policy_commencement, "%d/%m/%Y").date()
        except Exception:
            comm_date = datetime.date.today()
            
    days_since_comm = (datetime.date.today() - comm_date).days
    
    # Normalise input text
    diagnosis_clean = diagnosis.strip().lower()
    
    # 1. Check for empty or too short diagnosis
    if len(diagnosis_clean) < 3:
        return f"Risk Level: High\nReason: Claim diagnosis details are missing or invalid.\nApproved Amount: Rs. 0\nRecommended Action: Reject"
        
    # 2. Check standard exclusions
    exclusion_keywords = ["congenital", "self-inflicted", "cosmetic", "alcohol", "narcotic", "drug abuse", "suicide", "addiction"]
    has_exclusion = any(exc in diagnosis_clean for exc in exclusion_keywords)
    if has_exclusion:
        return f"Risk Level: Fraudulent\nReason: Diagnosis matches policy exclusions (congenital disease, self-inflicted injury, cosmetic procedure, or substance abuse).\nApproved Amount: Rs. 0\nRecommended Action: Reject"

    # 3. Check if claimed amount is valid
    if claimed_amount <= 0:
        return f"Risk Level: High\nReason: Claimed amount (Rs. {claimed_amount:,}) is invalid.\nApproved Amount: Rs. 0\nRecommended Action: Reject"

    # 4. Check for explicitly non-medical, silly, or general wellness categories (do not approve)
    silly_reasons = [
        "marriage", "wedding", "trip", "vacation", "flight", "travel", "groceries", "grocer",
        "shopping", "hotel", "gift", "car", "rent", "restaurant", "cafe", "furniture", 
        "appliance", "movie", "entertainment", "recreation", "spa", "weight loss", "routine checkup", 
        "routine health checkup", "preventative checkup"
    ]
    is_silly = any(word in diagnosis_clean for word in silly_reasons)
    if is_silly:
        return f"Risk Level: High\nReason: Diagnosis '{diagnosis}' is a non-medical or silly reason (e.g. marriages, weddings, trips, groceries) and is not a valid medical reason for health/claim coverage.\nApproved Amount: Rs. 0\nRecommended Action: Reject"

    # 5. Check for severe or major medical reasons (needs to be investigated)
    severe_reasons = [
        "operation", "surgery", "surgical", "bypass", "angioplasty", "stent",
        "cancer", "tumor", "carcinoma", "leukemia", "chemotherapy", "oncology",
        "accident", "major damage", "major injury", "illness", "treatment plan",
        "hospitalization", "admission", "viral fever", "acute viral fever", "fever"
    ]
    is_severe = any(word in diagnosis_clean for word in severe_reasons)
    if is_severe:
        return f"Risk Level: Medium\nReason: Severe/major medical reason (operations, cancer treatments, accidents with major damages, illness, treatment plans) requires manual review and investigation.\nApproved Amount: Rs. 0\nRecommended Action: Investigate"

    # 6. Check standard mild medical reasons by amount
    mild_medical_keywords = ["fever", "viral", "flu", "cold", "cough", "gastroenteritis"]
    is_mild = any(word in diagnosis_clean for word in mild_medical_keywords)
    if is_mild and claimed_amount > 50000:
        return f"Risk Level: High\nReason: Claimed amount (Rs. {claimed_amount:,}) exceeds the Rs. 50,000 threshold for standard mild medical claims. Flagged for investigation.\nApproved Amount: Rs. 0\nRecommended Action: Investigate"

    # 7. Check standard medical reasons (fever, viral, flu, cold, dengue, malaria, typhoid, pneumonia, etc.)
    valid_medical_keywords = [
        "fever", "viral", "dengue", "malaria", "typhoid", "influenza", "flu", "cold",
        "gastroenteritis", "pneumonia", "tuberculosis", "covid", "corona", "appendicitis",
        "hernia", "gallbladder", "cholecystectomy", "fracture", "burns"
    ]
    is_valid_reason = any(word in diagnosis_clean for word in valid_medical_keywords)
    if not is_valid_reason:
        return f"Risk Level: High\nReason: Claim diagnosis '{diagnosis}' is unrecognized or not standard. Flagged for review.\nApproved Amount: Rs. 0\nRecommended Action: Investigate"

    # 8. Check wait periods & prior claim status
    if 0 <= days_since_comm < 30:
        return f"Risk Level: High\nReason: Claim filed within {days_since_comm} days of policy commencement (within the 30-day waiting period/pre-existing condition risk).\nApproved Amount: Rs. 0\nRecommended Action: Investigate"
        
    if last_claim_status == "Rejected":
        return f"Risk Level: Medium\nReason: Prior claim was recently rejected; profile flagged for investigation.\nApproved Amount: Rs. 0\nRecommended Action: Investigate"

    # 9. Calculate standard approval (cap at sum_insured if needed)
    if claimed_amount > sum_insured:
        approved_amount = sum_insured
        return f"Risk Level: Low\nReason: Claim details look standard, but claimed amount exceeds the sum insured. Approved up to the sum insured limit of Rs. {sum_insured:,}.\nApproved Amount: Rs. {approved_amount:,}\nRecommended Action: Approve"
    else:
        approved_amount = claimed_amount
        return f"Risk Level: Low\nReason: Claim details look standard and amount is within policy limits.\nApproved Amount: Rs. {approved_amount:,}\nRecommended Action: Approve"

FRAUD_SYSTEM_INSTRUCTION = """
You are the Fraud Detector Sub-Agent for InsureVoice AI.
Your role is to analyze submitted claims and flag potential fraud or high risk.

Guidelines:
1. ALWAYS use the verify_fraud_risk_tool to evaluate risk.
2. Provide a clear and spoken-friendly summary of your findings (Risk Level, Reason, Approved Amount, Action). Make sure you state the approved amount clearly.
3. Keep your response concise and conversational, suitable for read-aloud voice playback.
"""

def get_fraud_agent(customer_profile: dict or None = None) -> Agent:
    instruction = FRAUD_SYSTEM_INSTRUCTION
    if customer_profile:
        # Extract commencement date, sum insured, last claim status
        pols = customer_profile.get("existing_policies", [])
        sum_insured = 500000.0
        if pols:
            benefit = pols[0].get("benefit", "").lower()
            if "10 lakh" in benefit:
                sum_insured = 1000000.0
            elif "5 lakh" in benefit:
                sum_insured = 500000.0
                
        last_status = customer_profile.get("last_claim_status") or "Paid"
        commencement = "2025-11-14"  # standard default commencement
        
        profile_summary = f"""
Active Caller Profile Details (pass these to verify_fraud_risk_tool):
- Policy Commencement Date: {commencement}
- Sum Insured: {sum_insured}
- Last Claim Status: {last_status}
"""
        instruction += "\n" + profile_summary
        
    return Agent(
        name="fraud_detector",
        model="gemini-2.5-flash",
        instruction=instruction,
        tools=[verify_fraud_risk_tool]
    )
