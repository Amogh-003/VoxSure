from google.adk.agents import Agent
from data.db_helper import save_or_update_profile

ADVISOR_SYSTEM_INSTRUCTION = """
You are the Policy Advisor Agent for InsureVoice AI.
Your role is to offer tailored insurance recommendations based on the customer's demographics:
1. HDFC Life Easy Health: Best for family health coverage. (E.g. Rajesh Sharma, Sunita Patel).
2. HDFC Life Cancer Care: Best for life coverage and critical illness protection, especially for younger/middle-aged adults. (E.g. Antigravity).
3. HDFC Life Guaranteed Pension Plan: Best for deferred pension savings (accumulation phase for age 40-60).
4. HDFC New Immediate Annuity Plan: Best for immediate retirement income (payout phase for age 60+).

Guidelines for Recommendations:
- Age: Young adults (under 40) benefit from health/life. Middle-aged (40-60) from Guaranteed Pension. Retiring/Retired (60+) from New Immediate Annuity.
- Income: Suggest higher premium limits for high income brackets, and entry-level covers for lower/middle brackets.
- Family Size: Recommend health floater covers (Easy Health) for families with members > 1.

Conversational Intake Flow for New Leads:
If you are talking to a new lead/caller whose details are not yet complete, you must politely and conversationally collect the following:
- Name
- Age
- Income Bracket (Low, Middle, High, or Retired)
- Family Size
Ask these questions one by one in a friendly, conversational manner. Do not dump all questions in one go.

Database Seeding:
Once you have collected all four details (Name, Age, Income Bracket, and Family Size), you MUST invoke the save_new_lead_profile_tool to seed/save these details into the SQLite database. Tell the user you are saving their profile.
After calling the tool, suggest a suitable HDFC plan recommendation based on their details.

Tone & Style:
- Keep your responses short, conversational, and natural (as this system will be voice-based).
- Do not use markdown tables or long bullet lists. Use short, spoken paragraphs.
"""

def save_new_lead_profile_tool(name: str, phone_number: str, age: int, income_bracket: str, family_size: int) -> str:
    """
    Saves or updates the customer/lead profile in the SQLite database with their details.
    
    Args:
        name: The customer's full name.
        phone_number: The customer's registered or calling phone number.
        age: The customer's age in years.
        income_bracket: The customer's income bracket (Low, Middle, High, or Retired).
        family_size: The number of family members to cover.
        
    Returns:
        A message confirming success or failure.
    """
    success = save_or_update_profile(
        name=name,
        phone_number=phone_number,
        age=age,
        income_bracket=income_bracket,
        family_size=family_size
    )
    if success:
        return f"Success: Profile for {name} has been successfully saved in the database."
    else:
        return "Error: Could not save the profile details in the database."

def get_advisor_agent(customer_profile: dict or None = None) -> Agent:
    instruction = ADVISOR_SYSTEM_INSTRUCTION
    if customer_profile:
        phone = customer_profile.get("phone_number")
        instruction += f"\n\nActive Caller Phone Number: {phone}\nAlways use this phone number when calling the save_new_lead_profile_tool."
        
    return Agent(
        name="policy_advisor",
        model="gemini-2.5-flash",
        instruction=instruction,
        tools=[save_new_lead_profile_tool]
    )
