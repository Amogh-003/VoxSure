import re
from google.adk.agents import Agent
from data.db_helper import save_or_update_profile, lookup_customer

def update_customer_db_tool(name: str, phone_number: str, age: int, income_bracket: str, family_size: int) -> str:
    """
    Updates or inserts the SQLite database customer record with their demographic details.
    
    Args:
        name: The full name of the customer.
        phone_number: The calling or registered phone number.
        age: The age of the customer.
        income_bracket: The customer's income bracket (Low, Middle, High, or Retired).
        family_size: The family size / number of members to cover.
        
    Returns:
        A confirmation message indicating success or failure.
    """
    success = save_or_update_profile(
        name=name,
        phone_number=phone_number,
        age=age,
        income_bracket=income_bracket,
        family_size=family_size
    )
    if success:
        return f"Database Sync Success: SQLite record updated for {name} ({phone_number})."
    else:
        return "Database Sync Error: Failed to update SQLite record."

SUMMARY_SYSTEM_INSTRUCTION = """
You are the Call Summary Agent for InsureVoice AI.
Your role is to analyze a completed call's chat history and perform the following tasks:
1. Formulate a concise summary of the conversation. Focus on the caller's main concern (e.g. claim filed, query about operation, policy renewal, or coverage advice).
2. Identify and extract any changes or new values for caller demographics mentioned during the call (Name, Age, Income Bracket, Family Size).
3. If any demographic updates are found (especially for new leads or updated customers), you MUST call the update_customer_db_tool to save these changes to SQLite.
4. Output a summary report of the call, including:
   - Call Summary: (Concise paragraph describing what happened in the call)
   - Extracted Customer Details (ONLY display this section for NEW leads/customers to verify details; do NOT include this section for existing customers)
   - SQLite Sync Status: (Confirm if database was updated/inserted)
   - Full History of Call Summary (under a header "### 💬 Conversation Turn History"): List ALL turns of the call, formatting each turn exactly as:
     * User: "User's query/question text"
     * Response: "Assistant's response text"
"""

def get_call_summary_agent() -> Agent:
    """
    Returns the Call Summary Agent with update_customer_db_tool registered.
    """
    return Agent(
        name="call_summary_agent",
        model="gemini-2.5-flash",
        instruction=SUMMARY_SYSTEM_INSTRUCTION,
        tools=[update_customer_db_tool]
    )

def generate_mock_call_summary(chat_history: list, phone_number: str) -> str:
    """
    Locally parses the chat history without Gemini API to extract details,
    updates SQLite database, and returns a formatted call summary.
    """
    customer = lookup_customer(phone_number)
    name = customer["name"] if customer else "New Lead"
    age = customer["age"] if customer else 30
    income = customer["income_bracket"] if customer else "Middle"
    family = customer["family_size"] if customer else 2
    
    # Determine if this is a new lead (new customer)
    is_new = True
    if customer:
        pols = customer.get("existing_policies", [])
        if pols and len(pols) > 0:
            is_new = False
        else:
            is_new = bool(customer.get("is_new_lead"))
            
    discussion_points = []
    has_renewed = False
    has_claimed = False
    
    # Scan assistant questions and user answers
    for idx, msg in enumerate(chat_history):
        content = msg["content"].lower()
        role = msg["role"]
        
        # Check for claim filing or renewals in conversation
        if "renewed" in content or "renewal payment" in content:
            has_renewed = True
        if "filed successfully" in content or "claim document extracted" in content:
            has_claimed = True
            
        if role == "user" and idx > 0:
            prev_content = chat_history[idx - 1]["content"].lower()
            if "name, please" in prev_content or "your full name" in prev_content or "may i know your name" in prev_content:
                name = msg["content"].strip()
            elif "age, please" in prev_content or "know your age" in prev_content:
                age_match = re.search(r'\d+', msg["content"])
                if age_match:
                    age = int(age_match.group())
            elif "income bracket" in prev_content or "annual income" in prev_content:
                val = msg["content"].lower()
                if "low" in val:
                    income = "Low"
                elif "high" in val:
                    income = "High"
                elif "retired" in val:
                    income = "Retired"
                else:
                    income = "Middle"
            elif "family members" in prev_content or "how many family" in prev_content:
                fam_match = re.search(r'\d+', msg["content"])
                if fam_match:
                    family = int(fam_match.group())
                    
    # Update SQLite record
    success = save_or_update_profile(
        name=name,
        phone_number=phone_number,
        age=age,
        income_bracket=income,
        family_size=family
    )
    
    sync_status = "Updated/Inserted SQLite record successfully" if success else "No database update required or failed"
    
    summary_parts = []
    if has_claimed:
        summary_parts.append("The customer uploaded a medical bill and successfully filed a new pending claim.")
    if has_renewed:
        summary_parts.append("The customer processed their renewal payment and successfully extended their policy coverage.")
    if not summary_parts:
        summary_parts.append("The caller discussed their insurance coverage, inquired about policies/benefits, or completed demographic intake.")
        
    summary_text = " ".join(summary_parts)
    
    # Format the full turn history transcript
    history_turns = []
    for msg in chat_history:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            history_turns.append(f"- **User**: \"{content}\"")
        elif role == "assistant":
            history_turns.append(f"- **Response**: \"{content}\"")
            
    history_transcript = "\n".join(history_turns) if history_turns else "No conversation turns recorded."
    
    # Conditionally format the extracted details section only for new leads
    details_section = ""
    if is_new:
        details_section = f"""- **Extracted Customer Details (New Lead Verification):**
  - Name: {name}
  - Age: {age}
  - Income Bracket: {income}
  - Family Size: {family}
"""
        
    return f"""### 📝 Offline Call Summary Report
- **Call Summary:** {summary_text}
- **Caller Phone:** {phone_number}
{details_section}- **SQLite Database Sync:** {sync_status} (Offline execution)

### 💬 Conversation Turn History:
{history_transcript}"""
