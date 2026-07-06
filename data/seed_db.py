import csv
import json
import os
import sqlite3
import re
import pypdf

# Define directories
data_dir = os.path.dirname(os.path.abspath(__file__))
dataset_dir = os.path.join(os.path.dirname(data_dir), "Dataset")
csv_path = os.path.join(data_dir, "customers.csv")
db_path = os.path.join(data_dir, "insurance.db")

# Phone number mapping for the 10 PDF customers + 3 specific additional profiles
phone_mapping = {
    "Ramesh Kumar Naidu": "+919876543210",
    "Priya Subramaniam": "+919876543211",
    "Arvind Deshpande": "+919876543212",
    "Fatima Sheikh": "+919876543213",
    "Suresh Pillai": "+919876543214",
    "Nikhil Verma": "+919876543215",
    "Ananya Das": "+919876543216",
    "Harpreet Singh Gill": "+919876543217",
    "Divya Reddy": "+919876543218",
    "Manoj Chauhan": "+919876543219"
}

def clean_premium(prem_str):
    if not prem_str:
        return 0
    cleaned = re.sub(r"[^\d]", "", prem_str)
    return int(cleaned) if cleaned.isdigit() else 0

def extract_pdf_records(file_name, is_annuity=True):
    pdf_path = os.path.join(dataset_dir, file_name)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Required dataset PDF not found: {pdf_path}")
        
    reader = pypdf.PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"
        
    records = re.split(r"\[Synthetic\s+sample\s+record", full_text, flags=re.IGNORECASE)
    parsed = {}
    
    for idx, r in enumerate(records[1:], 1):
        name_match = re.search(r"Dear\s+([A-Za-z\s]+),", r)
        name = name_match.group(1).strip() if name_match else "Unknown"
        
        pol_num = "Unknown"
        pol_match = re.search(r"Policy\s+number:\s*(\w+)", r, re.IGNORECASE)
        if pol_match:
            pol_num = pol_match.group(1).strip()
            
        premium_val = 0
        if is_annuity:
            prem_match = re.search(r"Premium/Purchase\s+Price\s+Paid\s*\(excluding\s*GST\)\s*\n\s*Rs\.\s*([\d,]+)", r, re.IGNORECASE)
            if prem_match:
                premium_val = clean_premium(prem_match.group(1))
        else:
            prem_match = re.search(r"Annualised\s+Premium/\s*Single\s*Premium\s*\n\s*Rs\.\s*([\d,]+)", r, re.IGNORECASE)
            if prem_match:
                premium_val = clean_premium(prem_match.group(1))
            else:
                prem_match2 = re.search(r"Premium\s+per\s+Frequency\s*\n\s*Rs\.\s*([\d,]+)", r, re.IGNORECASE)
                if prem_match2:
                    premium_val = clean_premium(prem_match2.group(1))
                    
        # Benefit description
        option = "Unknown"
        if is_annuity:
            opt_match = re.search(r"Plan\s+Option\s*\n\s*(.*?)\n", r, re.IGNORECASE)
            if opt_match:
                option = opt_match.group(1).strip()
        else:
            option = "Deferred Pension savings plan with guaranteed vesting additions"
            
        # Nominee Details
        nominee = "Unknown"
        relation = "Unknown"
        nom_match = re.search(r"Nominee's\s+Name\s*\n\s*(.*?)\n", r, re.IGNORECASE)
        if nom_match:
            nominee = nom_match.group(1).strip()
        rel_match = re.search(r"Relationship\s+with\s+the\s+Life\s+Assured\s*\n\s*(.*?)\n", r, re.IGNORECASE)
        if rel_match:
            relation = rel_match.group(1).strip()
            
        # Age
        age = 60
        age_matches = re.findall(r"Age\s+on\s+Risk\s+Commencement\s+Date\s*\n\s*(\d+)", r, re.IGNORECASE)
        if age_matches:
            age = int(age_matches[0])
        else:
            age_matches2 = re.findall(r"Age\s+on\s+the\s+Risk\s+Commencement\s+Date\s*\n\s*(\d+)", r, re.IGNORECASE)
            if age_matches2:
                age = int(age_matches2[0])
                
        parsed[name] = {
            "policy_number": pol_num,
            "premium": premium_val,
            "option": option,
            "nominee": nominee,
            "relationship": relation,
            "age": age
        }
    return parsed

print("Extracting records from Immediate Annuity PDF...")
annuity_data = extract_pdf_records("HDFC_New_Immediate_Annuity_Plan_10_Synthetic_Individuals.pdf", is_annuity=True)

print("Extracting records from Guaranteed Pension PDF...")
pension_data = extract_pdf_records("HDFC_Guaranteed_Pension_Plan_10_Synthetic_Individuals.pdf", is_annuity=False)

# Realistic claim and renewal histories for the 10 core customers
customer_histories = {
    "Ramesh Kumar Naidu": {"claim_date": "2025-03-10", "claim_status": "Paid", "renewal_date": "2026-08-15"},
    "Priya Subramaniam": {"claim_date": "2025-11-04", "claim_status": "Rejected", "renewal_date": "2026-11-04"},
    "Arvind Deshpande": {"claim_date": "2025-06-20", "claim_status": "Paid", "renewal_date": "2026-09-30"},
    "Fatima Sheikh": {"claim_date": "2025-05-18", "claim_status": "Paid", "renewal_date": "2026-10-12"},
    "Suresh Pillai": {"claim_date": "2025-02-15", "claim_status": "Paid", "renewal_date": "2026-07-22"},
    "Nikhil Verma": {"claim_date": "2025-09-01", "claim_status": "Paid", "renewal_date": "2026-12-05"},
    "Ananya Das": {"claim_date": "2025-04-10", "claim_status": "Paid", "renewal_date": "2026-08-10"},
    "Harpreet Singh Gill": {"claim_date": "2025-04-12", "claim_status": "Paid", "renewal_date": "2026-09-14"},
    "Divya Reddy": {"claim_date": "2025-08-05", "claim_status": "Paid", "renewal_date": "2026-10-25"},
    "Manoj Chauhan": {"claim_date": "2025-01-20", "claim_status": "Rejected", "renewal_date": "2026-07-15"}
}

# Combine records for the 10 users
combined_users = []
for idx, name in enumerate(phone_mapping.keys(), 1):
    a_rec = annuity_data.get(name, {})
    p_rec = pension_data.get(name, {})
    
    policies = []
    if a_rec:
        policies.append({
            "policy_number": a_rec["policy_number"],
            "type": "New Immediate Annuity",
            "premium": a_rec["premium"],
            "benefit": a_rec["option"],
            "nominee": f"{a_rec['nominee']} ({a_rec['relationship']})"
        })
    if p_rec:
        policies.append({
            "policy_number": p_rec["policy_number"],
            "type": "Guaranteed Pension Plan",
            "premium": p_rec["premium"],
            "benefit": p_rec["option"],
            "nominee": f"{p_rec['nominee']} ({p_rec['relationship']})"
        })
        
    age = a_rec.get("age", 60)
    hist = customer_histories.get(name, {"claim_date": "", "claim_status": "", "renewal_date": ""})
    
    combined_users.append({
        "customer_id": idx,
        "phone_number": phone_mapping[name],
        "name": name,
        "age": age,
        "income_bracket": "",
        "family_size": "",
        "existing_policies": json.dumps(policies),
        "last_claim_date": hist["claim_date"],
        "last_claim_status": hist["claim_status"],
        "renewal_due_date": hist["renewal_date"],
        "preferred_language": "en",
        "is_new_lead": False
    })

# Add the requested profiles from Cancer Care and Easy Health PDFs
# 1. Antigravity - Cancer Care
combined_users.append({
    "customer_id": 11,
    "phone_number": "+919876543220",
    "name": "Antigravity",
    "age": 30,
    "income_bracket": "",
    "family_size": "",
    "existing_policies": json.dumps([
        {
            "policy_number": "HCC0384762310",
            "type": "HDFC Life Cancer Care",
            "premium": 15000,
            "benefit": "Gold Plan - 100% payout on Major Cancer Diagnosis & 3-year Premium Waiver",
            "nominee": "AI Developer (Creator)"
        }
    ]),
    "last_claim_date": "2025-09-12",
    "last_claim_status": "Paid",
    "renewal_due_date": "2026-12-01",
    "preferred_language": "en",
    "is_new_lead": False
})

# 2. Rajesh Sharma - Easy Health
combined_users.append({
    "customer_id": 12,
    "phone_number": "+919876543221",
    "name": "Rajesh Sharma",
    "age": 45,
    "income_bracket": "",
    "family_size": "",
    "existing_policies": json.dumps([
        {
            "policy_number": "HEH0948576231",
            "type": "HDFC Life Easy Health",
            "premium": 25000,
            "benefit": "Optima Restore Health Cover - Rs 10 Lakh Sum Insured",
            "nominee": "Aarti Sharma (Wife)"
        }
    ]),
    "last_claim_date": "2025-06-11",
    "last_claim_status": "Paid",
    "renewal_due_date": "2026-08-20",
    "preferred_language": "en",
    "is_new_lead": False
})

# 3. Sunita Patel - Easy Health
combined_users.append({
    "customer_id": 13,
    "phone_number": "+919876543222",
    "name": "Sunita Patel",
    "age": 38,
    "income_bracket": "",
    "family_size": "",
    "existing_policies": json.dumps([
        {
            "policy_number": "HEH0948576232",
            "type": "HDFC Life Easy Health",
            "premium": 22000,
            "benefit": "Optima Restore Health Cover - Rs 5 Lakh Sum Insured",
            "nominee": "Amit Patel (Husband)"
        }
    ]),
    "last_claim_date": "2025-10-05",
    "last_claim_status": "Rejected",
    "renewal_due_date": "2026-09-05",
    "preferred_language": "en",
    "is_new_lead": False
})

# 4. Karan Johar - Cancer Care
combined_users.append({
    "customer_id": 14,
    "phone_number": "+919876543223",
    "name": "Karan Johar",
    "age": 50,
    "income_bracket": "High",
    "family_size": 3,
    "existing_policies": json.dumps([
        {
            "policy_number": "HCC0384762311",
            "type": "HDFC Life Cancer Care",
            "premium": 18000,
            "benefit": "Silver Plan - 100% payout on Major Cancer Diagnosis",
            "nominee": "Hiroo Johar (Mother)"
        }
    ]),
    "last_claim_date": "2025-12-01",
    "last_claim_status": "Paid",
    "renewal_due_date": "2026-12-15",
    "preferred_language": "en",
    "is_new_lead": False
})

# 5. Deepika Padukone - Easy Health
combined_users.append({
    "customer_id": 15,
    "phone_number": "+919876543224",
    "name": "Deepika Padukone",
    "age": 35,
    "income_bracket": "High",
    "family_size": 2,
    "existing_policies": json.dumps([
        {
            "policy_number": "HEH0948576233",
            "type": "HDFC Life Easy Health",
            "premium": 12000,
            "benefit": "Daily Hospital Cash Benefit Option (DHCB)",
            "nominee": "Ranveer Singh (Husband)"
        }
    ]),
    "last_claim_date": "2025-07-22",
    "last_claim_status": "Paid",
    "renewal_due_date": "2026-07-22",
    "preferred_language": "en",
    "is_new_lead": False
})

# 6. Virat Kohli - Easy Health
combined_users.append({
    "customer_id": 16,
    "phone_number": "+919876543225",
    "name": "Virat Kohli",
    "age": 37,
    "income_bracket": "High",
    "family_size": 3,
    "existing_policies": json.dumps([
        {
            "policy_number": "HEH0948576234",
            "type": "HDFC Life Easy Health",
            "premium": 28000,
            "benefit": "Surgical Benefit Option - 138 listed Surgeries",
            "nominee": "Anushka Sharma (Wife)"
        }
    ]),
    "last_claim_date": "2025-08-10",
    "last_claim_status": "Paid",
    "renewal_due_date": "2026-08-10",
    "preferred_language": "en",
    "is_new_lead": False
})

# 7. Vikram Seth - Guaranteed Pension Plan
combined_users.append({
    "customer_id": 17,
    "phone_number": "+919876543226",
    "name": "Vikram Seth",
    "age": 62,
    "income_bracket": "Middle",
    "family_size": 1,
    "existing_policies": json.dumps([
        {
            "policy_number": "HGP0987654321",
            "type": "Guaranteed Pension Plan",
            "premium": 45000,
            "benefit": "Deferred Pension savings plan with guaranteed vesting additions",
            "nominee": "Leila Seth (Mother)"
        }
    ]),
    "last_claim_date": "2025-11-20",
    "last_claim_status": "Paid",
    "renewal_due_date": "2026-11-20",
    "preferred_language": "en",
    "is_new_lead": False
})

# 8. Arundhati Roy - New Immediate Annuity
combined_users.append({
    "customer_id": 18,
    "phone_number": "+919876543227",
    "name": "Arundhati Roy",
    "age": 58,
    "income_bracket": "Middle",
    "family_size": 2,
    "existing_policies": json.dumps([
        {
            "policy_number": "HIA0987654322",
            "type": "New Immediate Annuity",
            "premium": 150000,
            "benefit": "Annuity Option A: Life Annuity with Single Premium",
            "nominee": "Mary Roy (Sister)"
        }
    ]),
    "last_claim_date": "2025-04-30",
    "last_claim_status": "Paid",
    "renewal_due_date": "2026-09-10",
    "preferred_language": "en",
    "is_new_lead": False
})

# Extract and parse the 10 Easy Health policyholders from HDFC-Life-Easy-Health-FILLED-10-Holders.pdf
# and link them to their Cancer Care policies
try:
    print("Extracting records from Easy Health PDF...")
    eh_pdf_path = os.path.join(dataset_dir, "HDFC-Life-Easy-Health-FILLED-10-Holders.pdf")
    eh_reader = pypdf.PdfReader(eh_pdf_path)
    
    # Cancer Care sum insureds for policy 0 to 9
    cc_sum_insureds = [2000000, 500000, 2000000, 500000, 1500000, 2500000, 2000000, 2000000, 1500000, 2000000]
    
    # Realistic claim histories for the 10 new individuals
    eh_claims = [
        {"claim_date": "2025-05-14", "claim_status": "Paid"},
        {"claim_date": None, "claim_status": None},
        {"claim_date": "2025-08-01", "claim_status": "Rejected"},
        {"claim_date": None, "claim_status": None},
        {"claim_date": "2025-10-12", "claim_status": "Paid"},
        {"claim_date": None, "claim_status": None},
        {"claim_date": "2025-03-22", "claim_status": "Paid"},
        {"claim_date": None, "claim_status": None},
        {"claim_date": "2025-12-05", "claim_status": "Rejected"},
        {"claim_date": None, "claim_status": None}
    ]
    
    for i in range(10):
        start_page = i * 4
        p1_text = eh_reader.pages[start_page].extract_text()
        p3_text = eh_reader.pages[start_page + 2].extract_text()
        p4_text = eh_reader.pages[start_page + 3].extract_text()
        
        p1_lines = [l.strip() for l in p1_text.split("\n") if l.strip()]
        p3_lines = [l.strip() for l in p3_text.split("\n") if l.strip()]
        p4_lines = [l.strip() for l in p4_text.split("\n") if l.strip()]
        
        # Parse Page 1 Bottom
        p1_bottom = p1_lines[-15:]
        policy_num = None
        for idx, line in enumerate(p1_bottom):
            if re.search(r'EH220000000\d', line):
                policy_num = line
                phone = p1_bottom[idx-2]
                address = p1_bottom[idx-3]
                name = p1_bottom[idx-4]
                commencement_date = p1_bottom[idx-5]
                break
                
        # Parse Page 3 Bottom
        p3_bottom = p3_lines[-22:]
        client_id = None
        for idx, line in enumerate(p3_bottom):
            if line.startswith("ID: CL"):
                client_id = line.split("ID: ")[1].strip()
                dob = p3_bottom[idx+4]
                age_str = p3_bottom[idx+5]
                age = int(re.search(r'\d+', age_str).group())
                option = p3_bottom[idx+11]
                sum_insured_str = p3_bottom[idx+12]
                premium_str = p3_bottom[idx+13]
                nominee_name = p3_bottom[idx+17]
                break
                
        # Parse Page 4 Bottom
        p4_bottom = p4_lines[-10:]
        nominee_dob = p4_bottom[0]
        nominee_address = None
        for line in p4_bottom:
            if re.search(r'\d{5,6}', line):
                nominee_address = line
                break
                
        # Clean premium string
        eh_premium = clean_premium(premium_str)
        
        # Calculate Cancer Care Premium
        cc_sum_insured = cc_sum_insureds[i]
        cc_premium = int(cc_sum_insured * 0.0075 * (1.05 ** (age - 30)))
        
        # Create policies list for this customer
        policies = [
            {
                "policy_number": policy_num,
                "type": "HDFC Life Easy Health",
                "premium": eh_premium,
                "benefit": f"Optima Restore Health Cover - Plan Option {option} - {sum_insured_str} Sum Insured",
                "nominee": f"{nominee_name} ({nominee_address})"
            },
            {
                "policy_number": f"CC330000000{i}",
                "type": "HDFC Life Cancer Care",
                "premium": cc_premium,
                "benefit": f"Silver Plan - 100% payout on Major Cancer Diagnosis - Rs. {cc_sum_insured:,} Sum Insured",
                "nominee": f"{nominee_name} ({nominee_address})"
            }
        ]
        
        # Construct renewal date
        comm_parts = commencement_date.split("/")
        if len(comm_parts) == 3:
            comm_year = int(comm_parts[2])
            renewal_year = 2026 if comm_year <= 2024 else 2027
            renewal_due_date = f"{renewal_year}-{comm_parts[1]}-{comm_parts[0]}"
        else:
            renewal_due_date = "2026-11-14"
            
        hist = eh_claims[i]
        
        combined_users.append({
            "customer_id": 19 + i,
            "phone_number": phone.replace("-", "").strip(),
            "name": name,
            "age": age,
            "income_bracket": "Middle",
            "family_size": 2,
            "existing_policies": json.dumps(policies),
            "last_claim_date": hist["claim_date"] or "",
            "last_claim_status": hist["claim_status"] or "",
            "renewal_due_date": renewal_due_date,
            "preferred_language": "en",
            "is_new_lead": False
        })
except Exception as e:
    print(f"Error parsing Easy Health PDF: {e}")

# Write to customers.csv
print(f"Writing parsed customers to: {csv_path}")
fields = ["customer_id", "phone_number", "name", "age", "income_bracket", "family_size", 
          "existing_policies", "last_claim_date", "last_claim_status", "renewal_due_date", 
          "preferred_language", "is_new_lead"]

with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for row in combined_users:
        writer.writerow(row)

# Recreate SQLite Database
print(f"Re-creating SQLite database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS customers")
cursor.execute("""
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT UNIQUE,
    name TEXT,
    age INTEGER,
    income_bracket TEXT,
    family_size INTEGER,
    existing_policies TEXT,
    last_claim_date TEXT,
    last_claim_status TEXT,
    renewal_due_date TEXT,
    preferred_language TEXT,
    is_new_lead BOOLEAN
)
""")

# Seed database
for row in combined_users:
    cursor.execute("""
    INSERT INTO customers (
        customer_id, phone_number, name, age, income_bracket, family_size,
        existing_policies, last_claim_date, last_claim_status, renewal_due_date,
        preferred_language, is_new_lead
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        row["customer_id"],
        row["phone_number"],
        row["name"],
        row["age"],
        None if not row["income_bracket"] else row["income_bracket"],
        None if not row["family_size"] else row["family_size"],
        row["existing_policies"],
        None if not row["last_claim_date"] else row["last_claim_date"],
        None if not row["last_claim_status"] else row["last_claim_status"],
        None if not row["renewal_due_date"] else row["renewal_due_date"],
        row["preferred_language"],
        0
    ))

conn.commit()
conn.close()
print("Successfully initialized and seeded database with Annuity, Pension, Cancer, and Easy Health plans!")
