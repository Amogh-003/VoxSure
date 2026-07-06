import sys
import os

# Put project root in path dynamically
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.db_helper import lookup_customer, create_lead, get_all_customers

print("=== Phase 1 Programmatic Verification (Real Data) ===")

# Test 1: Count total customers
customers = get_all_customers()
print(f"Total customers in database: {len(customers)}")
for c in customers:
    print(f" - ID {c['customer_id']}: {c['name']} (Phone: {c['phone_number']}, Policies: {len(c['existing_policies'])})")

# Test 2: Lookup Ramesh Kumar Naidu by phone and name
print("\nTest 2a: Lookup 'Ramesh Kumar Naidu' with raw number '9876543210'")
res = lookup_customer("9876543210")
if res and res["name"] == "Ramesh Kumar Naidu":
    print("SUCCESS: Found customer by phone:", res["name"])
else:
    print("FAILED: Could not retrieve Ramesh Kumar Naidu by phone.")

print("\nTest 2b: Lookup 'Ramesh Kumar Naidu' with exact name 'Ramesh Kumar Naidu'")
res = lookup_customer("Ramesh Kumar Naidu")
if res and res["name"] == "Ramesh Kumar Naidu":
    print("SUCCESS: Found customer by exact name!")
else:
    print("FAILED: Name search failed.")

print("\nTest 2c: Lookup 'Ramesh Kumar Naidu' with partial name 'Ramesh'")
res = lookup_customer("Ramesh")
if res and res["name"] == "Ramesh Kumar Naidu":
    print("SUCCESS: Found customer by partial name!")
else:
    print("FAILED: Partial name search failed.")

# Test 3: Lookup non-existent customer
print("\nTest 3: Lookup non-existent number '+919999999999'")
res = lookup_customer("+919999999999")
if res is None:
    print("SUCCESS: Correctly returned None for unknown caller!")
else:
    print("FAILED: Lookup returned data for unknown caller.")

# Test 4: Create new lead
print("\nTest 4: Creating new lead for 'Rajeev Malhotra' with '+919999999999'")
success = create_lead(
    name="Rajeev Malhotra",
    phone_number="+919999999999",
    age=42,
    income_bracket="High",
    family_size=3,
    existing_policies=[{"type": "Life Insurance"}]
)
if success:
    print("SUCCESS: Lead created successfully!")
    new_res = lookup_customer("+919999999999")
    if new_res and new_res["name"] == "Rajeev Malhotra":
        print("SUCCESS: Retrieved new lead successfully!")
        print("  Lead details:", new_res)
    else:
        print("FAILED: Created lead, but could not retrieve it.")
else:
    print("FAILED: Could not create lead.")

# Clean up lead for consistency
print("\nCleaning up test lead from database...")
import sqlite3
from data.db_helper import DB_PATH
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("DELETE FROM customers WHERE phone_number = '+919999999999'")
conn.commit()
conn.close()
print("Clean up done!")
print("\nVerification complete!")
