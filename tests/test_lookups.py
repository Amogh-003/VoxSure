import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.db_helper import lookup_customer, get_all_customers

customers = get_all_customers()
print(f"Found {len(customers)} customers in DB.")
for c in customers:
    name = c['name']
    phone = c['phone_number']
    
    # Test lookup by exact name
    res_name = lookup_customer(name)
    # Test lookup by phone number
    res_phone = lookup_customer(phone)
    # Test lookup by partial name (first word)
    first_word = name.split()[0]
    res_partial = lookup_customer(first_word)
    
    print(f"Customer: '{name}' | Phone: '{phone}'")
    print(f"  Exact Name lookup: {'SUCCESS' if res_name and res_name['name'] == name else 'FAILED'}")
    print(f"  Phone lookup:      {'SUCCESS' if res_phone and res_phone['name'] == name else 'FAILED'}")
    print(f"  Partial Name lookup ('{first_word}'): {'SUCCESS' if res_partial and res_partial['name'] == name else 'FAILED'}")
    print("-" * 50)
