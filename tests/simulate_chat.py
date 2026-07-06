import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.runners import InMemoryRunner, types
from agents.coordinator import get_agents
from data.db_helper import lookup_customer

# Ensure API Key is loaded
from dotenv import load_dotenv
load_dotenv()

# Match Arvind Deshpande
customer = lookup_customer("Arvind Deshpande")
print("Found customer:", customer["name"] if customer else "None")

# Instantiate agents
coordinator, advisor = get_agents(customer)
runner = InMemoryRunner(agent=coordinator, app_name="insure_voice_test")
runner.session_service.create_session_sync(
    app_name="insure_voice_test",
    user_id="user_1",
    session_id="session_1"
)

# Turn 1: Greeting trigger
print("\n--- Turn 1: Greeting Trigger ---")
try:
    events = runner.run(
        user_id="user_1",
        session_id="session_1",
        new_message=types.Content(role="user", parts=[types.Part(text="Incoming call connected. Greet me.")])
    )
    for event in events:
        if event.output:
            print("Coordinator:", event.output)
except Exception as e:
    print("Error Turn 1:", e)

# Turn 2: User question
print("\n--- Turn 2: User Question ---")
try:
    events2 = runner.run(
        user_id="user_1",
        session_id="session_1",
        new_message=types.Content(role="user", parts=[types.Part(text="What policies do you recommend for my age?")])
    )
    for event in events2:
        if event.output:
            print("Agent:", event.output)
except Exception as e:
    print("Error Turn 2:", e)

# Turn 3: User follow up
print("\n--- Turn 3: User Follow Up ---")
try:
    events3 = runner.run(
        user_id="user_1",
        session_id="session_1",
        new_message=types.Content(role="user", parts=[types.Part(text="And what about life insurance?")])
    )
    for event in events3:
        if event.output:
            print("Agent:", event.output)
except Exception as e:
    print("Error Turn 3:", e)
