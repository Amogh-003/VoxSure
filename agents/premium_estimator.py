import re
from google.adk.agents import Agent

def estimate_premium_tool(age: int, plan_type: str, sum_insured: float, option: str = "B") -> str:
    """
    Estimates the insurance premium or retirement annuity payout for HDFC policies.
    
    Args:
        age: The age of the policyholder.
        plan_type: The plan type name ('HDFC Life Easy Health', 'HDFC Life Cancer Care', 
                   'HDFC Life Guaranteed Pension Plan', 'HDFC New Immediate Annuity Plan').
        sum_insured: The requested sum insured or purchase price.
        option: The plan option code or letter (e.g. 'A', 'B', 'C', 'D', 'E', 'F'). Defaults to 'B'.
        
    Returns:
        A formatted string with the premium breakdown, GST, and total payable amount.
    """
    plan_clean = plan_type.lower()
    option = option.strip().upper() if option else "B"
    
    net_premium = 0
    gst_rate = 0.18
    payout_note = ""
    
    if "easy health" in plan_clean:
        if option == 'A':
            factor = 0.0272 * (age / 46.0)
        elif option == 'B':
            if age < 40:
                factor = 0.0125
            elif age < 43:
                factor = 0.0126
            else:
                factor = 0.0184
        elif option == 'D':
            factor = 0.0214 if age < 35 else 0.0146
        elif option == 'E':
            if age < 37:
                factor = 0.017
            elif age < 45:
                factor = 0.025
            else:
                factor = 0.0246
        elif option == 'F':
            factor = 0.013
        else:
            factor = 0.015
        net_premium = int(sum_insured * factor)
        gst_rate = 0.18
        
    elif "cancer care" in plan_clean:
        factor = min(0.0075 * (1.05 ** (age - 30)), 0.03)
        net_premium = int(sum_insured * factor)
        gst_rate = 0.18
        
    elif "pension" in plan_clean:
        net_premium = int(sum_insured)
        gst_rate = 0.045
        payout_note = f"This regular premium of Rs. {net_premium:,} will accumulate vesting additions over the policy term."
        
    elif "annuity" in plan_clean:
        net_premium = int(sum_insured)
        gst_rate = 0.018
        annual_payout = int(net_premium * 0.072)
        payout_note = f"This single premium purchase price will guarantee an immediate annual lifetime payout of approximately Rs. {annual_payout:,} (Rs. {int(annual_payout/12):,} monthly)."
        
    else:
        net_premium = int(sum_insured * 0.015)
        gst_rate = 0.18
        
    gst_amount = int(net_premium * gst_rate)
    total_premium = net_premium + gst_amount
    
    result = f"""
Estimated Premium Breakdown for {plan_type}:
- Net Premium/Purchase Price: Rs. {net_premium:,}
- GST ({int(gst_rate*100)}%): Rs. {gst_amount:,}
- Total Premium Payable: Rs. {total_premium:,}
"""
    if payout_note:
        result += f"\nNote: {payout_note}"
        
    return result

PREMIUM_SYSTEM_INSTRUCTION = """
You are the Premium Estimator Agent for InsureVoice AI.
Your role is to calculate and explain estimated premiums, taxes (GST), and potential annuity payouts to callers.

Guidelines:
1. ALWAYS use the estimate_premium_tool to calculate the premium. Do not try to guess or do the math yourself.
2. Clearly explain the premium breakdown (Net Premium, GST rate, and Total Premium) to the caller.
3. If they are looking at a Pension or Annuity plan, explain how the premium choice affects their future payouts.
4. Voice-Friendly Formatting: Keep responses concise, clear, and easy to understand when read aloud. Avoid using markdown tables or special characters. Use spoken, friendly paragraphs.
"""

def get_premium_estimator_agent() -> Agent:
    return Agent(
        name="premium_estimator",
        model="gemini-2.5-flash",
        instruction=PREMIUM_SYSTEM_INSTRUCTION,
        tools=[estimate_premium_tool]
    )
