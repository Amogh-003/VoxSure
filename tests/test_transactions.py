import sys
import os
import sqlite3

# Put parent directory in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.db_helper import file_claim_in_db, renew_policy_in_db, lookup_customer, get_db_connection

# We will use Virat Kohli's seeded profile for testing transactions
TEST_PHONE = "+919876543225"  # Virat Kohli

def run_tests():
    print("--- Running Claims & Renewals Transaction Tests ---")
    
    # 1. Inspect initial state
    cust_before = lookup_customer(TEST_PHONE)
    if not cust_before:
        print("Error: Test customer Virat Kohli not found. Make sure data/seed_db.py was run.")
        return
        
    print(f"Initial State for {cust_before['name']}:")
    print(f" - Last Claim Date: {cust_before['last_claim_date']}")
    print(f" - Last Claim Status: {cust_before['last_claim_status']}")
    print(f" - Renewal Due Date: {cust_before['renewal_due_date']}")
    
    # 2. Test Claim Filing
    print("\nFiling a claim for test customer...")
    success = file_claim_in_db(TEST_PHONE)
    print(f"file_claim_in_db returned: {success}")
    
    cust_after_claim = lookup_customer(TEST_PHONE)
    print(f"State after filing claim:")
    print(f" - Last Claim Date: {cust_after_claim['last_claim_date']}")
    print(f" - Last Claim Status: {cust_after_claim['last_claim_status']}")
    
    assert success == True
    assert cust_after_claim['last_claim_status'] == "Pending"
    print("Claim Filing Test: PASSED [SUCCESS]")
    
    # 3. Test Policy Renewal
    print("\nRenewing policy for test customer...")
    success_renew = renew_policy_in_db(TEST_PHONE)
    print(f"renew_policy_in_db returned: {success_renew}")
    
    cust_after_renew = lookup_customer(TEST_PHONE)
    print(f"State after policy renewal:")
    print(f" - Renewal Due Date: {cust_after_renew['renewal_due_date']}")
    
    assert success_renew == True
    print("Policy Renewal Test: PASSED [SUCCESS]")
    
    # 4. Cleanup / Reset to original seeded values so we keep tests repeatable
    print("\nCleaning up test customer database values...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        UPDATE customers
        SET last_claim_date = '2025-08-10', last_claim_status = 'Paid', renewal_due_date = '2026-08-10'
        WHERE phone_number = ?
        """, (TEST_PHONE,))
        conn.commit()
        print("Database cleaned up successfully.")
    finally:
        conn.close()

if __name__ == "__main__":
    run_tests()
