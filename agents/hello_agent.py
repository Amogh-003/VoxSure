import os
import sys
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner, types

# 1. Load environment variables from .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("\n[WARNING] GEMINI_API_KEY is not set in the .env file.")
    print("Please open the file '.env' at the root of this workspace and paste your Gemini API Key.")
    print("Example: GEMINI_API_KEY=AIzaSy...\n")
    sys.exit(0)

# Set the GOOGLE_API_KEY variable which Google ADK expects
os.environ["GOOGLE_API_KEY"] = api_key

# 2. Define the Agent
hello_agent = Agent(
    name="hello_agent",
    model="gemini-2.5-flash",
    instruction="You are a friendly welcome agent for InsureVoice AI. Greet the user warmly and say 'Hello! The InsureVoice AI environment is fully functional and ready to build.' Keep your response to a single sentence."
)

# 3. Instantiate the Runner
runner = InMemoryRunner(agent=hello_agent, app_name="insure_voice_hello")

# 4. Create Session synchronously
runner.session_service.create_session_sync(
    app_name="insure_voice_hello",
    user_id="test_user",
    session_id="test_session"
)

def run_test_chat(prompt: str):
    print(f"\nUser: {prompt}")
    print("Agent: ", end="", flush=True)
    
    try:
        # Wrap prompt in Content/Part structure
        msg = types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )
        
        # Run the agent session
        events = runner.run(
            user_id="test_user",
            session_id="test_session",
            new_message=msg
        )
        
        # Iterate over the yielded events and print outputs
        for event in events:
            # Check for errors in the event
            if event.error_message:
                print(f"\nError: {event.error_message}")
                return
                
            # Check if there is output content to show
            if event.output is not None:
                print(event.output, end="", flush=True)
            elif event.content is not None:
                try:
                    for part in event.content.parts:
                        if part.text:
                            print(part.text, end="", flush=True)
                except AttributeError:
                    pass
        print()
    except Exception as e:
        print(f"\nError running agent: {e}")

if __name__ == "__main__":
    print("=== InsureVoice AI Phase 0 Verification ===")
    prompt = "Hello! Are you working?"
    run_test_chat(prompt)
