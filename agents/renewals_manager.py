from google.adk.agents import Agent
from data.db_helper import renew_policy_in_db

def renew_policy_tool(phone_number: str) -> str:
    """
    Renews the customer's policy in the database for another year.
    
    Args:
        phone_number: The caller's registered phone number.
        
    Returns:
        A confirmation message indicating success or failure.
    """
    success = renew_policy_in_db(phone_number)
    if success:
        return "Success: Your policy has been successfully renewed. The new renewal date is set to one year from today."
    else:
        return "Error: Could not renew the policy. Please verify if the phone number is registered."

RENEWALS_SYSTEM_INSTRUCTION = """
You are the Renewals Manager Agent for InsureVoice AI.
Your role is to assist policyholders in checking policy deadlines, calculating premiums, and renewing their active plans.

Operational Rules:
1. Renewal Status: If the user asks about their renewal date or deadline, check their customer context and report it clearly.
2. Renew Policy: When the user requests to renew their policy, you must invoke the tool renew_policy_tool(phone_number="..."). Confirm the renewal instantly once the tool completes.
3. Multi-Modal Output: Formulate a single, direct answer. Your response will simultaneously drive the displayed text and the spoken voice response.
4. Voice-Friendly Formatting: Keep your responses concise, clear, and easy to understand when read aloud by a text-to-speech engine. Avoid using complex markdown tables, raw symbols, long bullet points, or special characters. Write in short, conversational paragraphs.
"""

def get_renewals_agent() -> Agent:
    """
    Returns the renewals manager agent with renew_policy_tool registered as a tool.
    """
    return Agent(
        name="renewals_manager",
        model="gemini-2.5-flash",
        instruction=RENEWALS_SYSTEM_INSTRUCTION,
        tools=[renew_policy_tool]
    )
