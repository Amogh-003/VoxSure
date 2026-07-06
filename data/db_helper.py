import sqlite3
import json
import os
import re

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "insurance.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_phone(phone: str) -> str:
    """Strips all non-digit characters and returns the last 10 digits."""
    if not phone:
        return ""
    cleaned = re.sub(r"\D", "", phone)
    return cleaned[-10:] if len(cleaned) >= 10 else cleaned

def lookup_customer(identifier: str) -> dict or None:
    """
    Looks up a customer in SQLite by checking either the last 10 digits of their phone number,
    or doing a case-insensitive match on their name.
    Returns a dict representation of the customer record, or None if not found.
    """
    if not identifier:
        return None
        
    conn = get_db_connection()
    conn.create_function("normalize_phone", 1, normalize_phone)
    cursor = conn.cursor()
    try:
        # Check if the identifier contains at least 3 digits to decide if it's a phone lookup
        cleaned_digits = re.sub(r"\D", "", identifier)
        if len(cleaned_digits) >= 3:
            cursor.execute(
                "SELECT * FROM customers WHERE normalize_phone(phone_number) = normalize_phone(?)",
                (identifier,)
            )
            row = cursor.fetchone()
        else:
            # First try exact case-insensitive name match
            cursor.execute(
                "SELECT * FROM customers WHERE LOWER(name) = LOWER(?)",
                (identifier.strip(),)
            )
            row = cursor.fetchone()
            if not row:
                # Try partial name match (LIKE)
                cursor.execute(
                    "SELECT * FROM customers WHERE name LIKE ?",
                    (f"%{identifier.strip()}%",)
                )
                row = cursor.fetchone()
                
        if row:
            data = dict(row)
            if data.get("existing_policies"):
                try:
                    data["existing_policies"] = json.loads(data["existing_policies"])
                except Exception:
                    data["existing_policies"] = []
            else:
                data["existing_policies"] = []
            return data
        return None
    finally:
        conn.close()

def create_lead(name: str, phone_number: str, age: int, income_bracket: str, family_size: int, existing_policies: list) -> bool:
    """
    Inserts a new lead into the SQLite database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO customers (
            phone_number, name, age, income_bracket, family_size,
            existing_policies, last_claim_date, last_claim_status, renewal_due_date,
            preferred_language, is_new_lead
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 'en', 1)
        """, (
            phone_number,
            name,
            age,
            income_bracket,
            family_size,
            json.dumps(existing_policies)
        ))
        conn.commit()
        try:
            from knowledge_base.generate_user_indexes import generate_all_user_indexes
            generate_all_user_indexes()
        except Exception as e:
            print(f"Error updating user indexes: {e}")
        return True
    except sqlite3.IntegrityError:
        # Phone number already exists
        return False
    finally:
        conn.close()

def get_all_customers() -> list:
    """Returns a list of all customer records for dashboard list view."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM customers")
        rows = cursor.fetchall()
        results = []
        for r in rows:
            data = dict(r)
            if data.get("existing_policies"):
                try:
                    data["existing_policies"] = json.loads(data["existing_policies"])
                except Exception:
                    data["existing_policies"] = []
            else:
                data["existing_policies"] = []
            results.append(data)
        return results
    finally:
        conn.close()

def save_or_update_profile(name: str, phone_number: str, age: int, income_bracket: str, family_size: int, existing_policies: list = None) -> bool:
    """
    Inserts a new profile if the phone number is new, or updates the existing name, age,
    income bracket, family size, and optionally existing policies if it already exists.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if phone number already exists
        cursor.execute("SELECT customer_id FROM customers WHERE phone_number = ?", (phone_number,))
        row = cursor.fetchone()
        policies_json = json.dumps(existing_policies) if existing_policies is not None else '[]'
        if row:
            # Update existing
            if existing_policies is not None:
                cursor.execute("""
                UPDATE customers
                SET name = ?, age = ?, income_bracket = ?, family_size = ?, existing_policies = ?
                WHERE phone_number = ?
                """, (name, age, income_bracket, family_size, policies_json, phone_number))
            else:
                cursor.execute("""
                UPDATE customers
                SET name = ?, age = ?, income_bracket = ?, family_size = ?
                WHERE phone_number = ?
                """, (name, age, income_bracket, family_size, phone_number))
        else:
            # Insert new lead
            cursor.execute("""
            INSERT INTO customers (
                phone_number, name, age, income_bracket, family_size,
                existing_policies, last_claim_date, last_claim_status, renewal_due_date,
                preferred_language, is_new_lead
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 'en', 1)
            """, (phone_number, name, age, income_bracket, family_size, policies_json))
        conn.commit()
        try:
            from knowledge_base.generate_user_indexes import generate_all_user_indexes
            generate_all_user_indexes()
        except Exception as e:
            print(f"Error updating user indexes: {e}")
        return True
    except Exception as e:
        print(f"Error saving/updating profile: {e}")
        return False
    finally:
        conn.close()

def file_claim_in_db(phone_number: str) -> bool:
    """
    Sets the customer's last claim date to today and status to 'Pending'.
    """
    import datetime
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        cursor.execute("""
        UPDATE customers
        SET last_claim_date = ?, last_claim_status = 'Pending'
        WHERE phone_number = ?
        """, (today_str, phone_number))
        conn.commit()
        try:
            from knowledge_base.generate_user_indexes import generate_all_user_indexes
            generate_all_user_indexes()
        except Exception as e:
            print(f"Error updating user indexes: {e}")
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error filing claim: {e}")
        return False
    finally:
        conn.close()

def renew_policy_in_db(phone_number: str) -> bool:
    """
    Sets the customer's renewal due date to one year from now.
    """
    import datetime
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        next_year_str = (datetime.date.today() + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        cursor.execute("""
        UPDATE customers
        SET renewal_due_date = ?
        WHERE phone_number = ?
        """, (next_year_str, phone_number))
        conn.commit()
        try:
            from knowledge_base.generate_user_indexes import generate_all_user_indexes
            generate_all_user_indexes()
        except Exception as e:
            print(f"Error updating user indexes: {e}")
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error renewing policy: {e}")
        return False
    finally:
        conn.close()
