import streamlit as st
import sys
import os
import base64
import re

# Ensure the parent directory is in the path so we can import db_helper and agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.db_helper import lookup_customer, create_lead, get_all_customers, save_or_update_profile, file_claim_in_db, renew_policy_in_db, get_db_connection
from data.voice_helper import synthesize_text_gcp, transcribe_audio_gcp

from google.adk.runners import InMemoryRunner, types
from agents.coordinator import get_agents
import streamlit.components.v1 as components
from data.sentiment_helper import detect_sentiment, get_sentiment_badge

# Declare voice recorder component pointing to the local HTML template directory
voice_rec_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_recorder")
voice_recorder = components.declare_component("voice_recorder", path=voice_rec_dir)

# Ensure API Key is correctly loaded
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key

def extract_relevant_sentences(context_text: str, query: str) -> str:
    """
    Splits the retrieved context into sentences and returns only the sentences 
    that contain query terms, keeping it short and direct.
    """
    if not context_text or "No matching clauses" in context_text or "No matching" in context_text:
        return "The VoxSure policy advisor does not have specific details about that policy. For detailed coverage, premium, and benefit information, please refer to your official policy document."
        
    sentences = re.split(r'(?<=[.!?])\s+', context_text)
    query_words = [w.lower() for w in re.findall(r'\b\w+\b', query) if len(w) > 2]
    
    # Exclude common stopwords from matching
    stopwords = {"what", "how", "when", "where", "which", "who", "whom", "this", "that", "these", "those", "have", "with", "your", "plan", "policy", "does", "rules", "based", "from"}
    query_words = [w for w in query_words if w not in stopwords]
    
    matched_sentences = []
    seen = set()
    for sentence in sentences:
        sent_lower = sentence.lower()
        if any(word in sent_lower for word in query_words) or len(query_words) == 0:
            # Clean up brackets and page markers
            clean_sent = re.sub(r'\[Source:.*?\]', '', sentence).strip()
            clean_sent = re.sub(r'Page:\s*\d+', '', clean_sent).strip()
            clean_sent = re.sub(r'\[Active Caller Policy Profile - Structural Index\]', '', clean_sent).strip()
            clean_sent = re.sub(r'\[.*?\]', '', clean_sent).strip()
            clean_sent = re.sub(r'<<.*?>>', '', clean_sent).strip()
            clean_sent = clean_sent.replace("*", "").replace("#", "").strip()
            # Normalize internal spacing
            clean_sent = re.sub(r'\s+', ' ', clean_sent)
            if clean_sent and clean_sent not in seen and len(clean_sent) > 10:
                seen.add(clean_sent)
                matched_sentences.append(clean_sent)
                
    if matched_sentences:
        # Return at most 3 matched sentences to keep it short and direct
        return " ".join(matched_sentences[:3])
    else:
        # Fallback to the first sentence of the retrieved text if query words aren't matching
        clean_first = re.sub(r'\[Source:.*?\]', '', sentences[0]).strip()
        clean_first = re.sub(r'Page:\s*\d+', '', clean_first).strip()
        clean_first = re.sub(r'\[Active Caller Policy Profile - Structural Index\]', '', clean_first).strip()
        clean_first = re.sub(r'\[.*?\]', '', clean_first).strip()
        clean_first = re.sub(r'<<.*?>>', '', clean_first).strip()
        clean_first = clean_first.replace("*", "").replace("#", "").strip()
        clean_first = re.sub(r'\s+', ' ', clean_first)
        return clean_first

def get_mock_agent_response(new_message) -> list:
    class MockEvent:
        def __init__(self, output):
            self.output = output
            
    text = ""
    if hasattr(new_message, "parts") and new_message.parts:
        part = new_message.parts[0]
        text = getattr(part, "text", "") if part else ""
    else:
        text = str(new_message)
        
    customer = lookup_customer(st.session_state.active_phone)
    name = customer["name"] if customer else "New Caller"
    
    output_text = ""
    text_lower = text.lower()
    
    # Context-retrieval for simple confirmation turns (e.g., "yes go ahead")
    confirm_words = {"yes", "go ahead", "sure", "ok", "yes go ahead", "yeah", "please", "do it", "confirm", "yep", "ok go ahead", "agree"}
    if text_lower.strip() in confirm_words:
        history = st.session_state.chat_history
        last_real_query = ""
        for msg in reversed(history):
            if msg["role"] == "user":
                val = msg["content"].lower().strip()
                if val not in confirm_words and len(val) > 3:
                    last_real_query = msg["content"]
                    break
        if last_real_query:
            text = last_real_query
            text_lower = text.lower()
    
    if "incoming call connected" in text_lower:
        if customer:
            policies_list = ", ".join([p["type"] for p in customer.get("existing_policies", [])])
            output_text = f"Hello {name}! Warm welcome to VoxSure. I see you have active coverage with us ({policies_list}). How can I help you today?"
        else:
            st.session_state.intake_name = None
            st.session_state.intake_age = None
            st.session_state.intake_income = None
            st.session_state.intake_family = None
            output_text = "Welcome to VoxSure! I see you are calling from a new number. May I know your full name, please?"
    elif not customer:
        history = st.session_state.chat_history
        assistant_msgs = [h["content"] for h in history if h["role"] == "assistant"]
        user_msgs = [h["content"] for h in history if h["role"] == "user"]
        
        last_question = assistant_msgs[-1].lower() if assistant_msgs else ""
        
        if "intake_name" not in st.session_state:
            st.session_state.intake_name = None
        if "intake_age" not in st.session_state:
            st.session_state.intake_age = None
        if "intake_income" not in st.session_state:
            st.session_state.intake_income = None
        if "intake_family" not in st.session_state:
            st.session_state.intake_family = None
        if "intake_plan" not in st.session_state:
            st.session_state.intake_plan = None
        if "intake_amount" not in st.session_state:
            st.session_state.intake_amount = None
            
        if last_question:
            last_user_ans = user_msgs[-1].strip() if user_msgs else ""
            if "name, please" in last_question or "may i know your name" in last_question or "your full name" in last_question:
                st.session_state.intake_name = last_user_ans
            elif "age, please" in last_question or "know your age" in last_question:
                age_match = re.search(r'\d+', last_user_ans)
                st.session_state.intake_age = int(age_match.group()) if age_match else 30
            elif "income bracket" in last_question or "annual income" in last_question:
                ans_lower = last_user_ans.lower()
                if "low" in ans_lower:
                    st.session_state.intake_income = "Low"
                elif "high" in ans_lower:
                    st.session_state.intake_income = "High"
                elif "retired" in ans_lower:
                    st.session_state.intake_income = "Retired"
                else:
                    st.session_state.intake_income = "Middle"
            elif "family members" in last_question or "how many family" in last_question:
                fam_match = re.search(r'\d+', last_user_ans)
                st.session_state.intake_family = int(fam_match.group()) if fam_match else 2
            elif "which plan" in last_question or "policy you want" in last_question or "policy type" in last_question:
                ans_lower = last_user_ans.lower()
                if "cancer" in ans_lower:
                    st.session_state.intake_plan = "HDFC Life Cancer Care"
                elif "annuity" in ans_lower:
                    st.session_state.intake_plan = "HDFC New Immediate Annuity Plan"
                elif "pension" in ans_lower:
                    st.session_state.intake_plan = "HDFC Life Guaranteed Pension Plan"
                else:
                    st.session_state.intake_plan = "HDFC Life Easy Health"
            elif "target coverage amount" in last_question or "coverage amount" in last_question or "limit you want" in last_question:
                val_match = re.search(r'(\d+)\s*(lakh)?', last_user_ans.lower())
                if val_match:
                    num = int(val_match.group(1))
                    if "lakh" in last_user_ans.lower() or val_match.group(2):
                        st.session_state.intake_amount = num * 100000
                    elif num < 100:
                        st.session_state.intake_amount = num * 100000
                    else:
                        st.session_state.intake_amount = num
                else:
                    st.session_state.intake_amount = 500000
                
        if not st.session_state.intake_name:
            output_text = "Welcome to VoxSure! I see you are calling from a new number. May I know your full name, please?"
        elif not st.session_state.intake_age:
            output_text = f"Thank you, {st.session_state.intake_name}. May I know your age, please?"
        elif not st.session_state.intake_income:
            output_text = "And what is your approximate annual income bracket (Low, Middle, High, or Retired)?"
        elif not st.session_state.intake_family:
            output_text = "Got it. And how many family members would you like to cover?"
        elif not st.session_state.intake_plan:
            output_text = "Which insurance plan would you like to enroll in? We offer HDFC Life Easy Health (family health), HDFC Life Cancer Care (cancer cover), HDFC New Immediate Annuity Plan, or HDFC Life Guaranteed Pension Plan."
        elif not st.session_state.intake_amount:
            output_text = "And what is your target coverage amount for this plan (e.g., 5 Lakh, 10 Lakh, or specify another number)?"
        else:
            name_val = st.session_state.intake_name
            age_val = st.session_state.intake_age
            income_val = st.session_state.intake_income
            family_val = st.session_state.intake_family
            plan_val = st.session_state.intake_plan
            amount_val = st.session_state.intake_amount
            phone_val = st.session_state.active_phone
            
            import random
            premium_est = int(amount_val * 0.012) if plan_val == "HDFC Life Easy Health" else int(amount_val * 0.008)
            new_policy = {
                "policy_number": f"HDFC{random.randint(10000, 99999)}",
                "type": plan_val,
                "premium": premium_est,
                "benefit": f"Rs. {amount_val:,} Sum Insured"
            }
            
            success = save_or_update_profile(
                name=name_val,
                phone_number=phone_val,
                age=age_val,
                income_bracket=income_val,
                family_size=family_val,
                existing_policies=[new_policy]
            )
            
            st.session_state.intake_name = None
            st.session_state.intake_age = None
            st.session_state.intake_income = None
            st.session_state.intake_family = None
            st.session_state.intake_plan = None
            st.session_state.intake_amount = None
            
            if success:
                output_text = f"Thank you, {name_val}! I have successfully saved your details and enrolled you in {plan_val} with Rs. {amount_val:,} coverage limit. Your policy number is {new_policy['policy_number']}. How can I assist you today?"
            else:
                output_text = f"Thank you, {name_val}. I had an issue saving your details, but based on your interest, I recommend enrolling in {plan_val} with Rs. {amount_val:,} coverage."
    elif any(word in text_lower for word in ["number", "details", "my policy"]) and not any(w in text_lower for w in ["recommend", "advice"]):
        if customer and customer.get("existing_policies"):
            pols = customer["existing_policies"]
            details = [f"{p['type']}: {p.get('policy_number')}" for p in pols]
            output_text = f"Your active policy details are:\n- " + "\n- ".join(details)
        else:
            output_text = "I couldn't find any active policy numbers associated with your name."
    elif any(word in text_lower for word in ["recommend", "recommendation", "advice", "suggest", "which plan", "suggest a policy", "coverage details for new", "opt for a plan", "what policy should"]):
        if customer:
            age = customer.get("age", 45)
            if age >= 60:
                output_text = f"Based on your profile (Age {age}), I highly recommend our HDFC New Immediate Annuity Plan to secure a steady retirement income stream. You already have an Annuity policy, but you can opt for top-ups."
            elif age >= 40:
                output_text = f"Based on your age of {age}, I recommend the HDFC Life Guaranteed Pension Plan. It's a great way to build your retirement savings with guaranteed vesting additions."
            else:
                output_text = "For younger individuals, I highly recommend our HDFC Life Cancer Care plan for critical illness cover, and HDFC Life Easy Health for family healthcare coverage."
    elif any(word in text_lower for word in ["estimate", "quote", "calculate"]):
        if customer:
            age = customer.get("age", 45)
            # Estimate premium for HDFC Life Easy Health
            net_prem = int(500000 * (0.0184 if age >= 43 else 0.0126))
            gst = int(net_prem * 0.18)
            tot = net_prem + gst
            output_text = f"[OFFLINE SIMULATION] Premium Estimate for HDFC Life Easy Health (Option B, Rs 500,000 Sum Insured, Age {age}):\n- Net Premium: Rs. {net_prem:,}\n- GST (18%): Rs. {gst:,}\n- Total Premium Payable: Rs. {tot:,}"
        else:
            output_text = "[OFFLINE SIMULATION] Please specify your age, plan option, and sum insured to calculate a premium quote."
    elif any(word in text_lower for word in ["bill", "upload", "apollo_bill", "png"]):
        if customer:
            success = file_claim_in_db(customer["phone_number"])
            if success:
                output_text = f"[OFFLINE SIMULATION] Claim Document Extracted and Filed Successfully:\n- Patient Name: {customer['name']} (Matched policyholder)\n- Hospital: Apollo Hospital\n- Diagnosis: Acute Viral Fever\n- Claimed Amount: Rs. 15,000\n- Date: 12-Oct-2025\n\nStatus: Filed successfully. Status is set to 'Pending'."
            else:
                output_text = "[OFFLINE SIMULATION] Error: Could not file the claim in the database."
        else:
            output_text = "[OFFLINE SIMULATION] I could not find a registered profile to file a claim under."
    elif any(word in text_lower for word in ["fraud", "risk", "suspicious"]):
        if customer:
            from agents.fraud_subagent import verify_fraud_risk_tool
            # Extract claimed amount from text if mentioned, else default to 15000
            claimed_amount = 15000.0
            amt_match = re.search(r'(?:rs\.?|rupees|amount of|claiming|\b)\s*([\d,]+)\b', text_lower)
            if amt_match:
                try:
                    val = float(amt_match.group(1).replace(",", ""))
                    if val > 100:  # avoid picking up small numbers like age or policy count
                        claimed_amount = val
                except:
                    pass
            
            # Extract diagnosis from text if mentioned, else default to "Acute Viral Fever"
            diagnosis = "Acute Viral Fever"
            if "grocery" in text_lower or "groceries" in text_lower:
                diagnosis = "groceries"
            elif "car" in text_lower or "repair" in text_lower:
                diagnosis = "car repair"
            elif "cosmetic" in text_lower:
                diagnosis = "cosmetic surgery"
            elif "congenital" in text_lower:
                diagnosis = "congenital disease"
            elif "cancer" in text_lower or "tumor" in text_lower:
                diagnosis = "cancer"
            elif "fever" in text_lower:
                diagnosis = "fever"
            elif "accident" in text_lower or "fracture" in text_lower:
                diagnosis = "accidental fracture"
                
            # Get sum insured limit from caller's policy
            sum_insured = 500000.0
            pols = customer.get("existing_policies", [])
            if pols:
                # Find sum insured in policy benefits description
                benefit = pols[0].get("benefit", "").lower()
                si_match = re.search(r'rs\.?\s*([\d,]+)\s*(?:lakh|sum insured)', benefit)
                if si_match:
                    try:
                        sum_insured = float(si_match.group(1).replace(",", ""))
                        if "lakh" in benefit:
                            sum_insured *= 100000
                    except:
                        pass
                elif "5 lakh" in benefit:
                    sum_insured = 500000.0
                elif "10 lakh" in benefit:
                    sum_insured = 1000000.0
                    
            last_status = customer.get("last_claim_status", "Paid")
            result = verify_fraud_risk_tool(
                policy_commencement="2025-11-14",
                diagnosis=diagnosis,
                claimed_amount=claimed_amount,
                sum_insured=sum_insured,
                last_claim_status=last_status
            )
            output_text = f"[OFFLINE SIMULATION] Fraud Risk Assessment:\n{result}"
        else:
            output_text = "[OFFLINE SIMULATION] No active caller profile to perform fraud risk assessment."
    elif any(word in text_lower for word in ["operation", "surgery", "treatment", "procedure", "illness", "disease", "hospitalization", "accident", "claim for", "eligibility", "eligible", "get the amount for", "cover for"]):
        if customer:
            from agents.fraud_subagent import verify_fraud_risk_tool
            # Try to extract the diagnosis/illness
            diagnosis = "Acute Viral Fever"
            for prep in ["for my", "for a", "claim for", "payout for", "coverage for", "pay for", "for"]:
                if prep in text_lower:
                    parts = text_lower.split(prep)
                    if len(parts) > 1 and len(parts[1].strip()) > 2:
                        raw_diag = parts[1].strip()
                        raw_diag = re.sub(r'[?.!,]', '', raw_diag)
                        diagnosis = raw_diag
                        break
            
            # Parse claimed amount if mentioned
            claimed_amount = 15000.0
            amt_match = re.search(r'(?:rs\.?|rupees|amount of|claiming|\b)\s*([\d,]+)\b', text_lower)
            if amt_match:
                try:
                    val = float(amt_match.group(1).replace(",", ""))
                    if val > 100:
                        claimed_amount = val
                except:
                    pass
                    
            # Get sum insured limit
            sum_insured = 500000.0
            pols = customer.get("existing_policies", [])
            if pols:
                benefit = pols[0].get("benefit", "").lower()
                si_match = re.search(r'rs\.?\s*([\d,]+)\s*(?:lakh|sum insured)', benefit)
                if si_match:
                    try:
                        sum_insured = float(si_match.group(1).replace(",", ""))
                        if "lakh" in benefit:
                            sum_insured *= 100000
                    except:
                        pass
                elif "5 lakh" in benefit:
                    sum_insured = 500000.0
                elif "10 lakh" in benefit:
                    sum_insured = 1000000.0
            
            last_status = customer.get("last_claim_status", "Paid")
            result = verify_fraud_risk_tool(
                policy_commencement="2025-11-14",
                diagnosis=diagnosis,
                claimed_amount=claimed_amount,
                sum_insured=sum_insured,
                last_claim_status=last_status
            )
            
            # Format friendly spoken output
            lines = result.split("\n")
            risk_level = "Low"
            reason = ""
            approved_amt = "Rs. 0"
            action = "Approve"
            for line in lines:
                if line.startswith("Risk Level:"):
                    risk_level = line.split(":", 1)[1].strip()
                elif line.startswith("Reason:"):
                    reason = line.split(":", 1)[1].strip()
                elif line.startswith("Approved Amount:"):
                    approved_amt = line.split(":", 1)[1].strip()
                elif line.startswith("Recommended Action:"):
                    action = line.split(":", 1)[1].strip()
                    
            if action == "Approve":
                output_text = f"Yes, your claim for {diagnosis} is approved. The approved amount is {approved_amt}. Reason: {reason}."
            elif action == "Reject":
                output_text = f"I'm sorry, but your claim for {diagnosis} cannot be approved. Reason: {reason}."
            else:
                output_text = f"Your claim for {diagnosis} requires further investigation. Reason: {reason}."
        else:
            output_text = "[OFFLINE SIMULATION] No active caller profile to perform claim evaluation."
    elif any(word in text_lower for word in ["premium", "premium details", "pay premium"]):
        if customer and customer.get("existing_policies"):
            pols = customer["existing_policies"]
            details = [f"{p['type']} (Policy: {p.get('policy_number')}): Rs. {p.get('premium'):,}" for p in pols]
            output_text = f"Here are your premium details:\n- " + "\n- ".join(details)
        else:
            output_text = "I couldn't find any active premium details. For new leads, premiums will be calculated once we choose a plan."
    elif any(word in text_lower for word in ["renewal", "renew"]):
        if any(w in text_lower for w in ["pay", "submit", "execute", "do it", "process", "yes", "confirm"]):
            if customer:
                success = renew_policy_in_db(customer["phone_number"])
                if success:
                    output_text = "Success! I have processed your renewal payment. Your policy has been renewed for another year."
                else:
                    output_text = "I encountered an issue processing your renewal. Please check your billing details."
            else:
                output_text = "I could not find a registered profile to renew."
        else:
            if customer and customer.get("renewal_due_date"):
                output_text = f"Your policy renewal is due on {customer['renewal_due_date']}. Would you like me to process the renewal payment now?"
            else:
                output_text = "I couldn't find any pending renewal due date for your profile."
    elif any(word in text_lower for word in ["claim", "claims"]):
        if any(w in text_lower for w in ["file", "submit", "apply", "register", "do it", "process", "yes", "confirm"]):
            if customer:
                success = file_claim_in_db(customer["phone_number"])
                if success:
                    output_text = "Success! A new claim has been successfully filed in the system. The status is set to 'Pending'."
                else:
                    output_text = "I encountered an issue filing your claim. Please contact support."
            else:
                output_text = "I could not find a registered profile to file a claim under."
        else:
            if customer and customer.get("last_claim_date"):
                output_text = f"Your last claim was filed on {customer['last_claim_date']} and the status is: {customer['last_claim_status']}. Would you like to file a new claim?"
            else:
                output_text = "There are no claims recorded on your profile. Would you like to file a new claim?"
    else:
        # General query: Fallback to local RAG search over policy documents
        from knowledge_base.retriever import retrieve_policy_context
        retrieved = retrieve_policy_context(text)
        output_text = extract_relevant_sentences(retrieved, text)
        
    return [MockEvent(output_text)]

def run_agent_with_retry(runner, new_message, max_retries=3, delay=2):
    import time
    last_error = None
    for attempt in range(max_retries):
        try:
            events = runner.run(
                user_id="user_1",
                session_id="session_1",
                new_message=new_message
            )
            event_list = list(events)
            
            # Check for errors wrapped inside Event objects
            has_error = False
            error_msg = ""
            for event in event_list:
                if hasattr(event, "error_message") and event.error_message:
                    has_error = True
                    error_msg = event.error_message
                    break
                    
            if has_error:
                if "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower() or "limit" in error_msg.lower() or "429" in error_msg:
                    return get_mock_agent_response(new_message)
                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        continue
                    else:
                        return get_mock_agent_response(new_message)
            
            return event_list
        except Exception as e:
            last_error = e
            if "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower() or "limit" in str(e).lower() or "429" in str(e):
                return get_mock_agent_response(new_message)
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    continue
                else:
                    return get_mock_agent_response(new_message)
            raise e
    return get_mock_agent_response(new_message)

def get_event_text(event):
    if hasattr(event, "output") and event.output:
        return event.output
    if hasattr(event, "message") and event.message and event.message.parts:
        part = event.message.parts[0]
        if hasattr(part, "text") and part.text:
            return part.text
    return ""

def save_session_state(active_phone, chat_history):
    import json
    state = {
        "active_phone": active_phone,
        "chat_history": chat_history
    }
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_state.json")
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass

def load_session_state():
    import json
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_state.json")
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_phone": "", "chat_history": []}

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="VoxSure - Agent Dashboard",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling (Slate & Indigo Rebrand)
st.markdown("""
<style>
    /* Dark Theme Core Styles */
    .stApp {
        background: radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.06) 0%, rgba(15, 23, 42, 0) 40%),
                    radial-gradient(circle at 90% 80%, rgba(14, 165, 233, 0.05) 0%, rgba(10, 14, 23, 0) 50%),
                    #090d16 !important;
        color: #f8fafc !important;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0d1220 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.04) !important;
    }
    
    /* Header styling */
    .title-gradient {
        background: linear-gradient(135deg, #818cf8 0%, #38bdf8 50%, #34d399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.7rem;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    .subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* Animations & Glow effects */
    @keyframes pulse-green {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.5); }
        70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.5); }
        70% { box-shadow: 0 0 0 8px rgba(244, 63, 94, 0); }
        100% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0); }
    }
    @keyframes pulse-yellow {
        0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.5); }
        70% { box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }
        100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
    }
    @keyframes glow-border {
        0% { border-color: rgba(99, 102, 241, 0.12); }
        50% { border-color: rgba(14, 165, 233, 0.25); }
        100% { border-color: rgba(99, 102, 241, 0.12); }
    }
    
    /* Card design system (Slate & Indigo Glassmorphism) */
    .glass-card {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.55) 0%, rgba(30, 41, 59, 0.38) 100%);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(99, 102, 241, 0.12);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
        transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
        animation: glow-border 8s infinite alternate;
    }
    .glass-card:hover {
        transform: translateY(-4px) scale(1.005);
        border-color: rgba(99, 102, 241, 0.35);
        box-shadow: 0 20px 40px -15px rgba(99, 102, 241, 0.18);
    }
    
    /* Custom Badges */
    .badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }
    .badge-success {
        background-color: rgba(16, 185, 129, 0.1);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }
    .badge-danger {
        background-color: rgba(244, 63, 94, 0.1);
        color: #fb7185;
        border: 1px solid rgba(244, 63, 94, 0.2);
    }
    .badge-warning {
        background-color: rgba(245, 158, 11, 0.1);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.2);
    }
    .badge-primary {
        background-color: rgba(99, 102, 241, 0.1);
        color: #818cf8;
        border: 1px solid rgba(99, 102, 241, 0.2);
    }
    
    /* Metric styling */
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Streamlit Button override - Fits the background and avoids generic white/grey look */
    div.stButton > button {
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%) !important;
        color: #818cf8 !important;
        border: 1px solid rgba(99, 102, 241, 0.3) !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, #312e81 0%, #1e1b4b 100%) !important;
        color: #ffffff !important;
        border-color: rgba(99, 102, 241, 0.6) !important;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.25) !important;
    }
    
    /* Streamlit TextInput/NumberInput/Selectbox background alignment */
    div[data-testid="stTextInput"] input, 
    div[data-testid="stNumberInput"] input, 
    div[data-testid="stSelectbox"] div[role="button"] {
        background-color: #0f172a !important;
        color: #f8fafc !important;
        border: 1px solid rgba(99, 102, 241, 0.2) !important;
        border-radius: 8px !important;
    }
    
    /* Modify secondary grey text for better contrast */
    .stMarkdown p, .stMarkdown li, span[data-testid="stWidgetLabel"] p, .stWidgetLabel label {
        color: #cbd5e1 !important;
    }
</style>
""", unsafe_allow_html=True)

# App Title Section
st.markdown('<div class="title-gradient">VoxSure</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Autonomous, Voice-First Customer Service Agent • Console Simulator</div>', unsafe_allow_html=True)

# ----------------- SIDEBAR: Simulator Controls & Parameters -----------------
st.sidebar.markdown("### 🛠️ App Parameters & Variables")
st.sidebar.write("Configure active caller settings injected into the agent context.")

# Initialize active phone and chat history persistently
if "initialized" not in st.session_state:
    saved = load_session_state()
    st.session_state.active_phone = saved.get("active_phone", "")
    st.session_state.chat_history = saved.get("chat_history", [])
    st.session_state.caller_sentiment = "Neutral"
    st.session_state.initialized = True

active_phone = st.session_state.active_phone

# Resolve customer from active_phone
customer = None
if active_phone:
    customer = lookup_customer(active_phone)

# Pre-fill sidebar parameters based on current resolved customer
if customer:
    init_name = customer["name"]
    init_phone = customer["phone_number"]
    init_age = int(customer["age"]) if customer.get("age") is not None else 30
    init_income = customer["income_bracket"] or "Middle"
    init_family = int(customer["family_size"]) if customer.get("family_size") is not None else 2
else:
    init_name = "New Caller"
    init_phone = active_phone if active_phone else "+919876543210"
    init_age = 30
    init_income = "Middle"
    init_family = 2

# Render parameter inputs in the sidebar
sidebar_name = st.sidebar.text_input("Caller Name:", value=init_name, key="sidebar_name")
sidebar_phone = st.sidebar.text_input("Phone Number:", value=init_phone, key="sidebar_phone")
sidebar_age = st.sidebar.number_input("Age:", min_value=1, max_value=120, value=init_age, key="sidebar_age")
sidebar_income = st.sidebar.selectbox("Income Bracket:", ["Low", "Middle", "High", "Retired"], index=["Low", "Middle", "High", "Retired"].index(init_income), key="sidebar_income")
sidebar_family = st.sidebar.number_input("Family Size:", min_value=1, max_value=20, value=init_family, key="sidebar_family")

# Create the dynamic customer profile dictionary to inject into agents
active_profile = {
    "name": sidebar_name,
    "phone_number": sidebar_phone,
    "age": sidebar_age,
    "income_bracket": sidebar_income,
    "family_size": sidebar_family,
    "existing_policies": customer.get("existing_policies", []) if customer else []
}

# Button to save or update the active profile in SQLite
if st.sidebar.button("💾 Inject & Save Profile to SQLite"):
    success = save_or_update_profile(
        name=sidebar_name,
        phone_number=sidebar_phone,
        age=sidebar_age,
        income_bracket=sidebar_income,
        family_size=sidebar_family
    )
    if success:
        st.sidebar.success(f"Profile for {sidebar_name} saved & injected!")
        st.session_state.active_phone = sidebar_phone
        # Reset chat history to force a new greeting with the correct name!
        st.session_state.chat_history = []
        save_session_state(sidebar_phone, [])
        st.rerun()
    else:
        st.sidebar.error("Failed to save profile details.")

# If the phone number input changes, reload session
if sidebar_phone != active_phone:
    st.session_state.active_phone = sidebar_phone
    st.session_state.chat_history = []
    save_session_state(sidebar_phone, [])
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 🗂️ Simulated Directory")
st.sidebar.write("Select a profile to load pre-filled database variables:")

# Fetch all customers to populate directory list
all_custs = get_all_customers()

# Render clickable customer buttons in sidebar
for cust in all_custs:
    role_desc = "Lead" if cust["is_new_lead"] else "Customer"
    btn_label = f"{cust['name']} ({role_desc})\n{cust['phone_number']}"
    if st.sidebar.button(btn_label, key=f"btn_{cust['customer_id']}"):
        st.session_state.active_phone = cust["phone_number"]
        st.session_state.chat_history = []
        save_session_state(cust["phone_number"], [])
        st.rerun()

# ----------------- MAIN SECTION: Core Loop -----------------
if st.session_state.active_phone:
    # Trigger Lookup
    customer = lookup_customer(st.session_state.active_phone)
    
    # Initialize dynamic agent runner session if caller changed
    caller_id = f"customer_{customer['customer_id']}" if customer else f"lead_{st.session_state.active_phone}"
    
    is_new_caller = False
    if "current_caller" not in st.session_state:
        st.session_state.current_caller = caller_id
        if not st.session_state.chat_history:
            is_new_caller = True
    elif st.session_state.current_caller != caller_id:
        st.session_state.current_caller = caller_id
        st.session_state.chat_history = []
        is_new_caller = True
        
    # Re-create the runner if the caller changed or if it doesn't exist in session state
    if "runner" not in st.session_state or is_new_caller:
        coordinator, advisor = get_agents(active_profile)
        st.session_state.runner = InMemoryRunner(agent=coordinator, app_name="insure_voice")
        st.session_state.runner.session_service.create_session_sync(
            app_name="insure_voice",
            user_id="user_1",
            session_id="session_1"
        )
        
    # Run the initial welcome greeting from the coordinator only for a new caller
    if is_new_caller:
        try:
            events = run_agent_with_retry(
                st.session_state.runner,
                types.Content(role="user", parts=[types.Part(text="Incoming call connected. Greet me.")])
            )
            greeting = ""
            for event in events:
                text = get_event_text(event)
                if text:
                    greeting += text + "\n"
            if greeting:
                st.session_state.chat_history.append({"role": "assistant", "content": greeting.strip()})
                save_session_state(st.session_state.active_phone, st.session_state.chat_history)
        except Exception as e:
            st.session_state.chat_history.append({"role": "assistant", "content": f"Call connected. (Session initialised. Error triggering greeting: {e})"})
            save_session_state(st.session_state.active_phone, st.session_state.chat_history)
            
    # Check for HTML5 voice transcript query parameter
    if "voice_input" in st.query_params and st.query_params["voice_input"]:
        voice_query = st.query_params["voice_input"]
        st.query_params.clear()
        st.session_state.chat_history.append({"role": "user", "content": voice_query})
        save_session_state(st.session_state.active_phone, st.session_state.chat_history)
        
        try:
            events = run_agent_with_retry(
                st.session_state.runner,
                types.Content(role="user", parts=[types.Part(text=voice_query)])
            )
            full_response = ""
            for event in events:
                text = get_event_text(event)
                if text:
                    full_response += text + "\n"
            if not full_response:
                full_response = "I'm listening. Could you please clarify that?"
        except Exception as e:
            full_response = f"Sorry, I encountered an issue: {e}"
            
        st.session_state.chat_history.append({"role": "assistant", "content": full_response.strip()})
        save_session_state(st.session_state.active_phone, st.session_state.chat_history)
        st.rerun()

    # --- Live Application Preview Header (AI Studio Look) ---
    st.markdown("""
    <div class="glass-card" style="padding: 12px 18px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; border-left: 4px solid #22c55e;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="height: 12px; width: 12px; background-color: #22c55e; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px #22c55e; animation: pulse 2s infinite;"></span>
            <strong style="color: #ffffff; font-size: 1.05rem;">VoxSure Status:</strong> <span style="color: #e2e8f0; font-weight: 500;">Connected</span>
        </div>
        <div style="color: #6366f1; font-weight: 700; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em;">
            Active Agent: Master Coordinator
        </div>
    </div>
    """, unsafe_allow_html=True)

    # SQLite Database Profile Summary (Collapsible Expander)
    with st.expander("🔍 SQLite Customer Database Profile Summary (Screen-Pop)", expanded=True):
        if customer:
            st.success(f"Incoming call detected from {customer['name']}! Instantly retrieved profile.")
            
            # Grid layout for general info
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"""
                <div class="glass-card">
                    <div class="metric-label">Caller Name</div>
                    <div class="metric-value">{customer['name']}</div>
                    <div style="margin-top: 10px;">
                        <span class="badge {'badge-primary' if not customer['is_new_lead'] else 'badge-warning'}">
                            {'Existing Customer' if not customer['is_new_lead'] else 'New Lead'}
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                sentiment_html = get_sentiment_badge(st.session_state.caller_sentiment)
                st.markdown(f"""
                <div class="glass-card">
                    <div class="metric-label">Phone Number</div>
                    <div class="metric-value">{customer['phone_number']}</div>
                    <div class="metric-label" style="margin-top: 10px;">Caller Sentiment</div>
                    <div style="margin-top: 6px;">
                        {sentiment_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            with col3:
                income_bracket = customer['income_bracket'] if customer['income_bracket'] else "N/A"
                family_size_str = f"{customer['family_size']} Members" if customer['family_size'] else "N/A"
                st.markdown(f"""
                <div class="glass-card">
                    <div class="metric-label">Age / Bracket</div>
                    <div class="metric-value">{customer['age']} yrs / {income_bracket}</div>
                    <div class="metric-label" style="margin-top: 10px;">Family Size</div>
                    <div style="font-weight:600; font-size:1.1rem; color: #ffffff;">{family_size_str}</div>
                </div>
                """, unsafe_allow_html=True)
                
            # Left/Right Column split for policies and claims
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown("### 📋 Existing Policies")
                
                policies = customer["existing_policies"]
                if policies:
                    for idx, pol in enumerate(policies, 1):
                        col_p1, col_p2, col_p3 = st.columns([1, 1, 2])
                        with col_p1:
                            st.markdown(f"**Policy:** `{pol.get('policy_number')}`")
                        with col_p2:
                            st.markdown(f"**Type:** {pol.get('type')}")
                        with col_p3:
                            premium_formatted = f"Rs. {pol.get('premium'):,}" if isinstance(pol.get('premium'), (int, float)) else f"Rs. {pol.get('premium')}"
                            st.markdown(f"**Premium:** {premium_formatted} | **Benefit:** {pol.get('benefit', 'N/A')}")
                        if idx < len(policies):
                            st.markdown("---")
                else:
                    st.info("No active policies associated with this caller profile.")
                st.markdown('</div>', unsafe_allow_html=True)
                
            with col_right:
                # Claims Summary Card
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown("### 🏥 Claim Summary")
                if customer["last_claim_date"]:
                    st.write(f"**Last Claim Date:** {customer['last_claim_date']}")
                    status = customer['last_claim_status']
                    badge_class = "badge-success" if status == "Approved" else ("badge-danger" if status == "Rejected" else "badge-warning")
                    st.markdown(f"**Status:** <span class='badge {badge_class}'>{status}</span>", unsafe_allow_html=True)
                else:
                    st.write("No claim history recorded.")
                    
                st.markdown("---")
                st.markdown("**Visual Claim Submission**")
                uploaded_bill = st.file_uploader(
                    "Upload medical bill (PNG/JPG/PDF):",
                    type=["png", "jpg", "jpeg", "pdf"],
                    key="claim_bill_uploader",
                    label_visibility="collapsed"
                )
                if uploaded_bill is not None:
                    import uuid
                    scratch_dir = r"C:\Users\Amogh\.gemini\antigravity-ide\brain\906692e9-ac57-49ef-9cf6-c7ab5a265542\scratch"
                    os.makedirs(scratch_dir, exist_ok=True)
                    file_ext = uploaded_bill.name.split(".")[-1]
                    temp_bill_path = os.path.join(scratch_dir, f"claim_bill_{uuid.uuid4().hex[:8]}.{file_ext}")
                    with open(temp_bill_path, "wb") as f:
                        f.write(uploaded_bill.getbuffer())
                        
                    st.info(f"Analyzing `{uploaded_bill.name}`...")
                    # Call extract_claim_from_doc_tool
                    from agents.claims_handler import extract_claim_from_doc_tool
                    result = extract_claim_from_doc_tool(st.session_state.active_phone, temp_bill_path)
                    
                    st.session_state.chat_history.append({"role": "user", "content": f"I have uploaded a claim document: {uploaded_bill.name}"})
                    st.session_state.chat_history.append({"role": "assistant", "content": result})
                    save_session_state(st.session_state.active_phone, st.session_state.chat_history)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
                

                # Renewals Card
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown("### ⏳ Renewals")
                if customer["renewal_due_date"]:
                    st.write(f"**Renewal Due Date:** {customer['renewal_due_date']}")
                    st.markdown("<span class='badge badge-warning'>Renewal Active</span>", unsafe_allow_html=True)
                else:
                    st.write("No renewal schedule available.")
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning(f"Phone number '{st.session_state.active_phone}' not registered in SQLite. The Policy Advisor agent will perform a conversational intake flow to register this new lead.")
        
        # --- LIVE AGENT WORKSPACE WITH TABS ---
        st.markdown("---")
        st.markdown("## 🛠️ Specialist Agent Interactive Workspace")
        st.write("Interact with each specialist agent independently or use the unified Voice Assistant console below.")
        
        # Create the tab containers
        tab_voice, tab_explainer, tab_estimator, tab_claims, tab_fraud, tab_renewals = st.tabs([
            "💬 Voice Assistant Console", 
            "📖 FAQ & Policy Explainer (RAG)", 
            "🧮 Premium Estimator", 
            "📋 Claims Vision Portal", 
            "🛡️ Fraud Detector", 
            "⏳ Renewals Manager"
        ])
        
        # ----------------- TAB 1: VOICE ASSISTANT CONSOLE -----------------
        with tab_voice:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            
            # Connection Status Badge
            if st.session_state.chat_history:
                st.markdown(
                    f"""
                    <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 20px; padding: 6px 14px; margin-bottom: 15px; animation: pulse-green 2s infinite;">
                        <span style="display: inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;"></span>
                        <span style="font-size: 0.85rem; color: #10b981; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;">Call Active • Connected</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"""
                    <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 20px; padding: 6px 14px; margin-bottom: 15px; animation: pulse-yellow 2s infinite;">
                        <span style="display: inline-block; width: 8px; height: 8px; background: #f59e0b; border-radius: 50%; box-shadow: 0 0 8px #f59e0b;"></span>
                        <span style="font-size: 0.85rem; color: #f59e0b; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;">Line Ready • Waiting</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
            st.markdown("### 💬 Live Agent Chat Console")
            st.write("Talk to the autonomous voice-agent system. The coordinator will route your queries to the appropriate advisor.")
            
            # 🎤 Streamlit Custom Component Voice input
            voice_transcript = voice_recorder(key="voice_mic")
            
            if "last_processed_voice" not in st.session_state:
                st.session_state.last_processed_voice = None
                
            if voice_transcript and voice_transcript != st.session_state.last_processed_voice:
                st.session_state.last_processed_voice = voice_transcript
                
                st.session_state.caller_sentiment = detect_sentiment(voice_transcript)
                st.session_state.chat_history.append({"role": "user", "content": voice_transcript})
                save_session_state(st.session_state.active_phone, st.session_state.chat_history)
                
                with st.chat_message("assistant"):
                    response_placeholder = st.empty()
                    response_placeholder.write("Thinking...")
                    try:
                        events = run_agent_with_retry(
                            st.session_state.runner,
                            types.Content(role="user", parts=[types.Part(text=voice_transcript)])
                        )
                        full_response = ""
                        for event in events:
                            text = get_event_text(event)
                            if text:
                                full_response += text + "\n"
                        if not full_response:
                            full_response = "I'm listening. Could you please clarify that?"
                        response_placeholder.write(full_response.strip())
                    except Exception as e:
                        full_response = f"Sorry, I encountered an issue: {e}"
                        response_placeholder.write(full_response)
                        
                    st.session_state.chat_history.append({"role": "assistant", "content": full_response.strip()})
                    save_session_state(st.session_state.active_phone, st.session_state.chat_history)
                    st.rerun()
            
            # Display chat messages
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
                    
            # Text-to-Speech (TTS) Auto-Play & Control panel for the latest agent message
            if st.session_state.chat_history:
                last_msg = st.session_state.chat_history[-1]
                if last_msg["role"] == "assistant":
                    tts_text = last_msg["content"].replace('"', '\\"').replace('\n', ' ')
                    
                    # 1. Attempt GCP Text-to-Speech synthesis
                    audio_bytes = None
                    if api_key:
                        audio_bytes = synthesize_text_gcp(last_msg["content"], api_key)
                        
                    if audio_bytes:
                        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                        audio_src = f"data:audio/mp3;base64,{audio_b64}"
                        
                        st.components.v1.html(
                            f"""
                            <div style="display: flex; align-items: center; justify-content: center; gap: 12px; background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 10px; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; height: 50px; box-sizing: border-box;">
                                <span style="font-size: 0.9rem; color: #a5b4fc; font-weight: 600;">🗣️ GCP Voice:</span>
                                <button id="play-btn" style="background: #22c55e; border: none; border-radius: 6px; padding: 6px 12px; color: white; cursor: pointer; font-weight: bold; display: flex; align-items: center; gap: 4px; transition: 0.2s;">Play ▶️</button>
                                <button id="pause-btn" style="background: #f59e0b; border: none; border-radius: 6px; padding: 6px 12px; color: white; cursor: pointer; font-weight: bold; display: flex; align-items: center; gap: 4px; transition: 0.2s;">Pause ⏸️</button>
                                <button id="stop-btn" style="background: #ef4444; border: none; border-radius: 6px; padding: 6px 12px; color: white; cursor: pointer; font-weight: bold; display: flex; align-items: center; gap: 4px; transition: 0.2s;">Stop ⏹️</button>
                                <div style="width: 1px; height: 20px; background: rgba(255,255,255,0.15); margin: 0 4px;"></div>
                                <span id="speech-status" style="font-size: 0.85rem; color: #10b981; font-weight: 500;">Autoplaying...</span>
                            </div>
                            <audio id="gcp-audio" src="{audio_src}"></audio>
                            <script>
                                const playBtn = document.getElementById('play-btn');
                                const pauseBtn = document.getElementById('pause-btn');
                                const stopBtn = document.getElementById('stop-btn');
                                const status = document.getElementById('speech-status');
                                const audio = document.getElementById('gcp-audio');
                                
                                const ttsText = "{tts_text}";
                                const storageKey = "last_spoken_text_gcp";
                                
                                audio.onplaying = () => {{
                                    status.innerText = "Speaking...";
                                    status.style.color = "#10b981";
                                }};
                                
                                audio.onpause = () => {{
                                    status.innerText = "Paused";
                                    status.style.color = "#f59e0b";
                                }};
                                
                                audio.onended = () => {{
                                    status.innerText = "Finished";
                                    status.style.color = "#94a3b8";
                                }};
                                
                                // Autoplay logic
                                if (localStorage.getItem(storageKey) !== ttsText && ttsText.trim() !== "") {{
                                    localStorage.setItem(storageKey, ttsText);
                                    audio.play().catch(e => {{
                                        status.innerText = "Click Play to Listen";
                                        status.style.color = "#94a3b8";
                                    }});
                                }} else if (ttsText.trim() !== "") {{
                                    status.innerText = "Idle";
                                    status.style.color = "#94a3b8";
                                }}
                                
                                playBtn.addEventListener('click', () => {{
                                    audio.play();
                                }});
                                
                                pauseBtn.addEventListener('click', () => {{
                                    audio.pause();
                                }});
                                
                                stopBtn.addEventListener('click', () => {{
                                    audio.pause();
                                    audio.currentTime = 0;
                                    status.innerText = "Stopped";
                                    status.style.color = "#ef4444";
                                }});
                            </script>
                            """,
                            height=75
                        )
                    else:
                        # 2. Fallback to Browser native speech synthesis if GCP fails or is offline
                        st.components.v1.html(
                            f"""
                            <div style="display: flex; align-items: center; justify-content: center; gap: 12px; background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 10px; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; height: 50px; box-sizing: border-box;">
                                <span style="font-size: 0.9rem; color: #94a3b8; font-weight: 600;">🗣️ Browser Voice:</span>
                                <button id="play-btn" style="background: #22c55e; border: none; border-radius: 6px; padding: 6px 12px; color: white; cursor: pointer; font-weight: bold; display: flex; align-items: center; gap: 4px; transition: 0.2s;">Play ▶️</button>
                                <button id="pause-btn" style="background: #f59e0b; border: none; border-radius: 6px; padding: 6px 12px; color: white; cursor: pointer; font-weight: bold; display: flex; align-items: center; gap: 4px; transition: 0.2s;">Pause ⏸️</button>
                                <button id="stop-btn" style="background: #ef4444; border: none; border-radius: 6px; padding: 6px 12px; color: white; cursor: pointer; font-weight: bold; display: flex; align-items: center; gap: 4px; transition: 0.2s;">Stop ⏹️</button>
                                <div style="width: 1px; height: 20px; background: rgba(255,255,255,0.15); margin: 0 4px;"></div>
                                <span id="speech-status" style="font-size: 0.85rem; color: #10b981; font-weight: 500;">Autoplaying...</span>
                            </div>
                            <script>
                                const playBtn = document.getElementById('play-btn');
                                const pauseBtn = document.getElementById('pause-btn');
                                const stopBtn = document.getElementById('stop-btn');
                                const status = document.getElementById('speech-status');
                                
                                const ttsText = "{tts_text}";
                                const storageKey = "last_spoken_text_browser";
                                
                                let utterance = null;
                                
                                function speak() {{
                                    window.speechSynthesis.cancel();
                                    utterance = new SpeechSynthesisUtterance(ttsText);
                                    utterance.lang = 'en-US';
                                    
                                    utterance.onstart = () => {{
                                        status.innerText = "Speaking...";
                                        status.style.color = "#10b981";
                                    }};
                                    
                                    utterance.onend = () => {{
                                        status.innerText = "Finished";
                                        status.style.color = "#94a3b8";
                                    }};
                                    
                                    utterance.onerror = (e) => {{
                                        if (e.error !== 'interrupted') {{
                                            status.innerText = "Error: " + e.error;
                                            status.style.color = "#ef4444";
                                        }}
                                    }};
                                    
                                    window.speechSynthesis.speak(utterance);
                                }}
                                
                                // Autoplay logic
                                if (localStorage.getItem(storageKey) !== ttsText && ttsText.trim() !== "") {{
                                    localStorage.setItem(storageKey, ttsText);
                                    speak();
                                }} else if (ttsText.trim() !== "") {{
                                    status.innerText = "Idle";
                                    status.style.color = "#94a3b8";
                                }}
                                
                                playBtn.addEventListener('click', () => {{
                                    if (window.speechSynthesis.paused) {{
                                        window.speechSynthesis.resume();
                                        status.innerText = "Speaking...";
                                        status.style.color = "#10b981";
                                    }} else if (!window.speechSynthesis.speaking) {{
                                        speak();
                                    }}
                                }});
                                
                                pauseBtn.addEventListener('click', () => {{
                                    if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {{
                                        window.speechSynthesis.pause();
                                        status.innerText = "Paused";
                                        status.style.color = "#f59e0b";
                                    }}
                                }});
                                
                                stopBtn.addEventListener('click', () => {{
                                    window.speechSynthesis.cancel();
                                    status.innerText = "Stopped";
                                    status.style.color = "#ef4444";
                                }});
                            </script>
                            """,
                            height=75
                        )
                    
            # GCP Speech-to-Text Audio File Uploader
            st.markdown('<div style="margin-top: 15px; margin-bottom: 15px;">', unsafe_allow_html=True)
            uploaded_audio = st.file_uploader(
                "🎙️ Upload an audio query (WAV/MP3/WebM) to transcribe via GCP Speech-to-Text:",
                type=["wav", "mp3", "webm"],
                key="stt_audio_uploader",
                label_visibility="collapsed"
            )
            if uploaded_audio is not None:
                audio_bytes = uploaded_audio.read()
                st.info("Transcribing audio via GCP STT API...")
                transcript = transcribe_audio_gcp(audio_bytes, api_key)
                if transcript:
                    st.success(f"Transcribed Text: **{transcript}**")
                    st.session_state.caller_sentiment = detect_sentiment(transcript)
                    st.session_state.chat_history.append({"role": "user", "content": transcript})
                    save_session_state(st.session_state.active_phone, st.session_state.chat_history)
                    
                    with st.spinner("Agent is generating response..."):
                        try:
                            events = run_agent_with_retry(
                                st.session_state.runner,
                                types.Content(role="user", parts=[types.Part(text=transcript)])
                            )
                            full_response = ""
                            for event in events:
                                text = get_event_text(event)
                                if text:
                                    full_response += text + "\n"
                            if not full_response:
                                full_response = "I'm listening. Could you please clarify that?"
                        except Exception as e:
                            full_response = f"Sorry, I encountered an issue: {e}"
                            
                        st.session_state.chat_history.append({"role": "assistant", "content": full_response.strip()})
                        save_session_state(st.session_state.active_phone, st.session_state.chat_history)
                    st.rerun()
                else:
                    st.error("GCP Speech-to-Text could not transcribe the file. (Verify your API key has GCP Speech-to-Text API enabled)")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Call Summary display
            if "call_summary" in st.session_state and st.session_state.call_summary:
                st.markdown('<div class="glass-card" style="border: 1px solid rgba(16, 185, 129, 0.3); background: rgba(16, 185, 129, 0.05); margin-bottom: 15px;">', unsafe_allow_html=True)
                st.markdown(st.session_state.call_summary)
                if st.button("🗑️ Dismiss Summary", key="btn_clear_summary", use_container_width=True):
                    st.session_state.call_summary = None
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
                
            # End Call Button
            if st.session_state.chat_history:
                if st.button("🔴 End Call & Summarize Session", key="btn_end_call", use_container_width=True):
                    with st.spinner("Call Summary Agent is formulating summary and updating database..."):
                        summary_result = ""
                        if api_key:
                            try:
                                from agents.call_summary_agent import get_call_summary_agent
                                summary_agent = get_call_summary_agent()
                                runner_sum = InMemoryRunner(agent=summary_agent, app_name="summary_app")
                                runner_sum.session_service.create_session_sync(app_name="summary_app", user_id="u1", session_id="s1")
                                
                                history_str = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in st.session_state.chat_history])
                                prompt = f"Caller Phone Number: {st.session_state.active_phone}\n\nChat History:\n{history_str}"
                                
                                events = runner_sum.run(user_id="u1", session_id="s1", new_message=types.Content(role="user", parts=[types.Part(text=prompt)]))
                                event_list = list(events)
                                for e in event_list:
                                    if hasattr(e, "error_message") and e.error_message:
                                        raise RuntimeError(e.error_message)
                                summary_result = "".join([get_event_text(e) for e in event_list if get_event_text(e)]).strip()
                                if not summary_result:
                                    raise RuntimeError("Empty response received from Call Summary agent.")
                            except Exception as e:
                                from agents.call_summary_agent import generate_mock_call_summary
                                summary_result = generate_mock_call_summary(st.session_state.chat_history, st.session_state.active_phone)
                        else:
                            from agents.call_summary_agent import generate_mock_call_summary
                            summary_result = generate_mock_call_summary(st.session_state.chat_history, st.session_state.active_phone)
                            
                        st.session_state.call_summary = summary_result
                        st.session_state.chat_history = []
                        save_session_state(st.session_state.active_phone, [])
                        st.rerun()
            
            # Chat input
            if user_input := st.chat_input("Speak to VoxSure..."):
                with st.chat_message("user"):
                    st.write(user_input)
                st.session_state.caller_sentiment = detect_sentiment(user_input)
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                save_session_state(st.session_state.active_phone, st.session_state.chat_history)
                
                with st.chat_message("assistant"):
                    response_placeholder = st.empty()
                    response_placeholder.write("Thinking...")
                    try:
                        events = run_agent_with_retry(
                            st.session_state.runner,
                            types.Content(role="user", parts=[types.Part(text=user_input)])
                        )
                        full_response = ""
                        for event in events:
                            text = get_event_text(event)
                            if text:
                                full_response += text + "\n"
                        if not full_response:
                            full_response = "I'm listening. Could you please clarify that?"
                        response_placeholder.write(full_response.strip())
                    except Exception as e:
                        full_response = f"Sorry, I encountered an issue: {e}"
                        response_placeholder.write(full_response)
                        
                    st.session_state.chat_history.append({"role": "assistant", "content": full_response.strip()})
                    save_session_state(st.session_state.active_phone, st.session_state.chat_history)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        # ----------------- TAB 2: FAQ & POLICY EXPLAINER (RAG) -----------------
        with tab_explainer:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("### 📖 FAQ & Policy Explainer Agent Workspace")
            st.write("Retrieve context directly from HDFC policy documents (Chroma vector DB) and formulate a response using the Explainer agent.")
            
            exp_query = st.text_input("Enter policy query (e.g. waiting periods, critical illness exclusions, revival rules):", value="waiting periods", key="exp_query_input")
            if st.button("🔍 Ask Policy Explainer Agent", key="btn_ask_explainer"):
                with st.spinner("Searching vector knowledge base and running Explainer..."):
                    from knowledge_base.retriever import retrieve_policy_context
                    retrieved_text = retrieve_policy_context(exp_query)
                    
                    st.markdown("### 📄 Retrieved Context from Policy Documents:")
                    st.info(retrieved_text if retrieved_text else "No matching policy context found.")
                    
                    # Formulate agent output
                    if api_key:
                        try:
                            from agents.explainer import get_explainer_agent
                            explainer_agent = get_explainer_agent()
                            runner_exp = InMemoryRunner(agent=explainer_agent, app_name="explainer_app")
                            runner_exp.session_service.create_session_sync(app_name="explainer_app", user_id="u1", session_id="s1")
                            events = runner_exp.run(user_id="u1", session_id="s1", new_message=types.Content(role="user", parts=[types.Part(text=f"Retrieved Context: {retrieved_text}\\n\\nQuestion: {exp_query}")]))
                            event_list = list(events)
                            for e in event_list:
                                if hasattr(e, "error_message") and e.error_message:
                                    raise RuntimeError(e.error_message)
                            ans = "".join([get_event_text(e) for e in event_list if get_event_text(e)]).strip()
                            if not ans:
                                raise RuntimeError("Empty response received from explainer agent.")
                        except Exception as e:
                            ans = extract_relevant_sentences(retrieved_text, exp_query)
                    else:
                        ans = extract_relevant_sentences(retrieved_text, exp_query)
                    
                    st.markdown("### 🎙️ Explainer Agent Response:")
                    st.success(ans)
                    
                    # Speak out response
                    st.components.v1.html(
                        f"""
                        <script>
                            window.speechSynthesis.cancel();
                            const utterance = new SpeechSynthesisUtterance("{ans.replace('"', '\\"').replace('\\n', ' ')}");
                            utterance.lang = 'en-US';
                            window.speechSynthesis.speak(utterance);
                        </script>
                        """,
                        height=0
                    )
            st.markdown('</div>', unsafe_allow_html=True)
            
        # ----------------- TAB 3: PREMIUM ESTIMATOR -----------------
        with tab_estimator:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("### 🧮 Premium Estimator Agent Workspace")
            st.write("Input parameters to estimate premium rates and pension vesting additions.")
            
            est_age = st.number_input("Policyholder Age:", min_value=18, max_value=100, value=customer['age'] if customer else 30, key="est_age_tab")
            est_plan = st.selectbox(
                "Select Insurance Plan:",
                ["HDFC Life Easy Health", "HDFC Life Cancer Care", "HDFC Life Guaranteed Pension Plan", "HDFC New Immediate Annuity Plan"],
                key="est_plan_tab"
            )
            est_si = st.number_input("Sum Insured / Purchase Price (Rs.):", min_value=50000, max_value=10000000, value=500000, step=50000, key="est_si_tab")
            est_opt = st.selectbox("Plan Option (Easy Health Options A-F):", ["A", "B", "C", "D", "E", "F"], index=1, key="est_opt_tab")
            
            if st.button("🧮 Run Premium Estimator Agent", key="btn_run_estimator"):
                from agents.premium_estimator import estimate_premium_tool
                result = estimate_premium_tool(age=est_age, plan_type=est_plan, sum_insured=est_si, option=est_opt)
                
                st.markdown("### 📊 Calculated Quote:")
                st.info(result)
                
                # Speak out response
                clean_speak = result.replace("\\n", " ").replace('"', '\\"')
                st.components.v1.html(
                    f"""
                    <script>
                        window.speechSynthesis.cancel();
                        const utterance = new SpeechSynthesisUtterance("{clean_speak}");
                        utterance.lang = 'en-US';
                        window.speechSynthesis.speak(utterance);
                    </script>
                    """,
                    height=0
                )
            st.markdown('</div>', unsafe_allow_html=True)
            
        # ----------------- TAB 4: CLAIMS VISION PORTAL -----------------
        with tab_claims:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("### 📋 Claims Agent Vision Portal")
            st.write("Upload medical bills to visually extract data and verify policies using Gemini Multimodal Vision.")
            
            claim_bill = st.file_uploader(
                "Upload claim invoice / receipt / discharge summary:",
                type=["png", "jpg", "jpeg", "pdf"],
                key="tab_claim_bill_uploader"
            )
            if claim_bill is not None:
                # Save file
                import uuid
                scratch_dir = r"C:\\Users\\Amogh\\.gemini\\antigravity-ide\\brain\\906692e9-ac57-49ef-9cf6-c7ab5a265542\\scratch"
                os.makedirs(scratch_dir, exist_ok=True)
                file_ext = claim_bill.name.split(".")[-1]
                temp_path = os.path.join(scratch_dir, f"claim_bill_{uuid.uuid4().hex[:8]}.{file_ext}")
                with open(temp_path, "wb") as f:
                    f.write(claim_bill.getbuffer())
                    
                if file_ext.lower() in ["png", "jpg", "jpeg"]:
                    st.image(claim_bill, caption="Uploaded Invoice Preview", width=400)
                else:
                    st.info(f"📄 Uploaded Document: `{claim_bill.name}` (PDF document cannot be previewed directly, click execute below to process)")
                
                if st.button("🚀 Execute Visual Claim Extraction", key="btn_run_claims_vision"):
                    with st.spinner("Extracting parameters and verifying client status..."):
                        from agents.claims_handler import extract_claim_from_doc_tool
                        result = extract_claim_from_doc_tool(st.session_state.active_phone, temp_path)
                        
                        st.markdown("### 📄 Extraction Result & DB Status:")
                        st.success(result)
                        
                        # Speak out status
                        clean_res = result.replace("\\n", " ").replace('"', '\\"')
                        st.components.v1.html(
                            f"""
                            <script>
                                window.speechSynthesis.cancel();
                                const utterance = new SpeechSynthesisUtterance("Claim document processed.");
                                utterance.lang = 'en-US';
                                window.speechSynthesis.speak(utterance);
                            </script>
                            """,
                            height=0
                        )
            st.markdown('</div>', unsafe_allow_html=True)
            
        # ----------------- TAB 5: FRAUD DETECTOR -----------------
        with tab_fraud:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("### 🛡️ Fraud Risk Evaluator Sub-agent")
            st.write("Assesses the active caller's claims for potential risk using multi-factor guidelines.")
            
            if customer:
                comm_date = "2025-11-14"  # Default matching Girindra Pau
                
                reasons_list = [
                    "Acute Viral Fever",
                    "Influenza (Flu)",
                    "Heart Surgery / Operation",
                    "Cancer chemotherapy treatment",
                    "Accident with major damages",
                    "Wedding ceremony",
                    "Trip to Goa / vacation",
                    "Weekly Groceries shopping",
                    "Cosmetic procedure / surgery",
                    "Other (Enter custom below)"
                ]
                selected_reason = st.selectbox(
                    "Select Claim Diagnosis / Illness:",
                    options=reasons_list,
                    index=0,
                    key="fraud_diag_select"
                )
                if selected_reason == "Other (Enter custom below)":
                    f_diag = st.text_input("Enter custom Diagnosis / Illness:", value="Acute Viral Fever", key="fraud_diag_input")
                else:
                    f_diag = selected_reason
                    
                f_amt = st.number_input("Claimed Amount (Rs.):", min_value=1000, max_value=5000000, value=15000, step=1000, key="fraud_amt_input")
                f_si = st.number_input("Policy Sum Insured Limit (Rs.):", min_value=50000, max_value=5000000, value=500000, step=50000, key="fraud_si_input")
                f_last_status = customer.get("last_claim_status", "Paid")
                
                if st.button("🛡️ Run Fraud Risk Evaluation", key="btn_run_fraud"):
                    from agents.fraud_subagent import verify_fraud_risk_tool
                    result = verify_fraud_risk_tool(
                        policy_commencement=comm_date,
                        diagnosis=f_diag,
                        claimed_amount=f_amt,
                        sum_insured=f_si,
                        last_claim_status=f_last_status
                    )
                    
                    st.markdown("### 🛡️ Fraud Sub-agent Evaluation Details:")
                    if "Fraudulent" in result:
                        st.error(result)
                    elif "High" in result:
                        st.warning(result)
                    elif "Medium" in result:
                        st.info(result)
                    else:
                        st.success(result)
                        
                    # Speak out risk result
                    st.components.v1.html(
                        f"""
                        <script>
                            window.speechSynthesis.cancel();
                            const utterance = new SpeechSynthesisUtterance("Fraud evaluation complete. {result.replace('\\n', ' ')}");
                            utterance.lang = 'en-US';
                            window.speechSynthesis.speak(utterance);
                        </script>
                        """,
                        height=0
                    )
            else:
                st.info("No active caller profile loaded to evaluate fraud risk.")
            st.markdown('</div>', unsafe_allow_html=True)
            
        # ----------------- TAB 6: RENEWALS MANAGER -----------------
        with tab_renewals:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("### ⏳ Renewals Manager Agent")
            st.write("Manage active caller renewal due dates and process payments.")
            
            if customer:
                st.markdown(f"**Policyholder Name:** {customer['name']}")
                st.markdown(f"**Renewal Due Date:** `{customer['renewal_due_date']}`")
                
                if st.button("💳 Trigger Renewal Payment & Process Renewals", key="btn_run_renewals_tab"):
                    with st.spinner("Processing transaction..."):
                        success = renew_policy_in_db(customer["phone_number"])
                        if success:
                            st.success("Success! Renewal premium paid and policy term extended.")
                            st.components.v1.html(
                                f"""
                                <script>
                                    window.speechSynthesis.cancel();
                                    const utterance = new SpeechSynthesisUtterance("Success! Renewal payment processed successfully.");
                                    utterance.lang = 'en-US';
                                    window.speechSynthesis.speak(utterance);
                                </script>
                                """,
                                height=0
                            )
                            st.rerun()
                        else:
                            st.error("Error processing renewal in database.")
            else:
                st.info("No active caller profile loaded to manage renewals.")
            st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("Waiting for incoming call... Select a caller profile from the sidebar directory or type a phone number.")
