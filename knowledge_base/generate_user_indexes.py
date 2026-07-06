import os
import json
import sys

# Ensure parent directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.db_helper import get_all_customers

USER_INDEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_indexes")

def generate_all_user_indexes():
    os.makedirs(USER_INDEX_DIR, exist_ok=True)
    customers = get_all_customers()
    for cust in customers:
        phone = cust.get("phone_number")
        if not phone:
            continue
        
        # Build the user index structure
        user_index = {
            "name": cust.get("name"),
            "phone_number": phone,
            "age": cust.get("age"),
            "income_bracket": cust.get("income_bracket"),
            "family_size": cust.get("family_size"),
            "existing_policies": cust.get("existing_policies", []),
            "last_claim_date": cust.get("last_claim_date"),
            "last_claim_status": cust.get("last_claim_status"),
            "renewal_due_date": cust.get("renewal_due_date"),
            "preferred_language": cust.get("preferred_language", "en"),
            "is_new_lead": bool(cust.get("is_new_lead"))
        }
        
        # Save as JSON file named by phone number
        filepath = os.path.join(USER_INDEX_DIR, f"{phone}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(user_index, f, indent=2)
            
    print(f"Generated user indexes for {len(customers)} customers in {USER_INDEX_DIR}")

if __name__ == "__main__":
    generate_all_user_indexes()
