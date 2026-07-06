import os
import re
from flask import Flask, request, Response
from data.db_helper import lookup_customer

app = Flask(__name__)

# Basic TwiML helper to construct Twilio responses without external twilio library dependency
def twiml_response(content: str) -> Response:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
{content}
</Response>"""
    return Response(xml, mimetype="text/xml")

@app.route("/voice", methods=["GET", "POST"])
def voice():
    """Initial Twilio voice webhook endpoint."""
    caller_phone = request.values.get("From", "")
    customer = lookup_customer(caller_phone)
    
    name = customer["name"] if customer else "valued customer"
    
    welcome_msg = f"Hello {name}. Welcome to InsureVoice A.I. How can I help you today?"
    if not customer:
        welcome_msg = "Welcome to InsureVoice A.I. We see you are calling from a new number. May I get your name, please?"
        
    gather = f"""    <Say voice="Polly.Kajal" language="en-IN">{welcome_msg}</Say>
    <Gather input="speech" action="/handle-speech" timeout="5" speechTimeout="auto">
    </Gather>
    <Say>We didn't receive any input. Goodbye.</Say>"""
    return twiml_response(gather)

@app.route("/handle-speech", methods=["GET", "POST"])
def handle_speech():
    """Processes user speech from Twilio and returns the agent's response."""
    user_speech = request.values.get("SpeechResult", "")
    caller_phone = request.values.get("From", "")
    
    if not user_speech:
        return twiml_response("<Say>I'm sorry, I couldn't hear you clearly. Please try again.</Say><Redirect>/voice</Redirect>")
        
    print(f"Twilio Call from {caller_phone} - User said: {user_speech}")
    
    # 1. Fetch active customer profile
    customer = lookup_customer(caller_phone)
    
    # 2. Call our agent routing logic (mock runner or live coordinator)
    response_text = ""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google.adk.runners import InMemoryRunner
            from google.genai import types
            from agents.coordinator import get_agents
            
            coord_agent, _ = get_agents(customer)
            runner = InMemoryRunner(agent=coord_agent, app_name="voice_app")
            
            # Simple session id matching phone number to persist context across call turns
            session_id = f"twilio_{caller_phone.replace('+', '')}"
            try:
                runner.session_service.create_session_sync(app_name="voice_app", user_id="twilio_user", session_id=session_id)
            except Exception:
                pass # Session may already exist
                
            events = runner.run(
                user_id="twilio_user",
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part(text=user_speech)])
            )
            
            # Extract text from events
            text_parts = []
            for e in events:
                if hasattr(e, "output") and e.output:
                    text_parts.append(str(e.output))
                elif hasattr(e, "text") and e.text:
                    text_parts.append(str(e.text))
            response_text = " ".join(text_parts).strip()
        except Exception as e:
            print(f"Error calling live agent: {e}")
            
    # If API fails or is not available, use the mock runner fallback
    if not response_text:
        # Simple offline mock response parser for Twilio calls
        if "renew" in user_speech.lower() or "pay" in user_speech.lower():
            response_text = "Your policy has been successfully renewed. The new renewal date is set to one year from today."
        elif "claim" in user_speech.lower() or "operation" in user_speech.lower() or "leg" in user_speech.lower():
            response_text = "I have filed your pending claim. Your diagnosis has been flagged for investigation by our fraud detector agent."
        elif "waiting" in user_speech.lower() or "periods" in user_speech.lower():
            response_text = "There is a standard 30-day waiting period for new health policies. Pre-existing diseases have a 2-year waiting period."
        else:
            response_text = "I'm listening. Could you please clarify your request?"
            
    print(f"Agent response to Twilio: {response_text}")
    
    # 3. Form TwiML to speak back response and gather next input
    xml_content = f"""    <Say voice="Polly.Kajal" language="en-IN">{response_text}</Say>
    <Gather input="speech" action="/handle-speech" timeout="5" speechTimeout="auto">
    </Gather>
    <Redirect>/voice</Redirect>"""
    return twiml_response(xml_content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Twilio Voice Integration Server starting on port {port}...")
    print("Use ngrok to expose this port (e.g. 'ngrok http 5000') and configure your Twilio Number's Webhook to http://your-ngrok-url/voice")
    app.run(host="0.0.0.0", port=port, debug=True)
