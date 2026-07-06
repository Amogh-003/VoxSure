import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.fraud_subagent import verify_fraud_risk_tool

def run_tests():
    print("--- Running AI Voice Assistant Agent Update Tests ---")
    
    # Test case 1: Valid medical reason within sum insured
    print("\nTest 1: Standard valid medical reason & amount")
    res1 = verify_fraud_risk_tool(
        policy_commencement="2025-06-01",
        diagnosis="Acute Viral Fever",
        claimed_amount=15000.0,
        sum_insured=500000.0,
        last_claim_status="Paid"
    )
    print(res1)
    assert "Risk Level: Medium" in res1
    assert "Approved Amount: Rs. 0" in res1
    assert "Recommended Action: Investigate" in res1
    print("Test 1: PASSED")
    
    # Test case 2: Claim amount exceeds sum insured limit (should approve up to sum insured)
    print("\nTest 2: Claimed amount exceeds sum insured")
    res2 = verify_fraud_risk_tool(
        policy_commencement="2025-06-01",
        diagnosis="Dengue treatment",
        claimed_amount=600000.0,
        sum_insured=500000.0,
        last_claim_status="Paid"
    )
    print(res2)
    assert "Risk Level: Low" in res2
    assert "Approved Amount: Rs. 500,000" in res2
    assert "exceeds the sum insured" in res2
    assert "Recommended Action: Approve" in res2
    print("Test 2: PASSED")

    # Test case 3: Exclusion keywords check (should reject with 0 approved amount)
    print("\nTest 3: Exclusion keywords (Cosmetic surgery)")
    res3 = verify_fraud_risk_tool(
        policy_commencement="2025-06-01",
        diagnosis="cosmetic nose job",
        claimed_amount=25000.0,
        sum_insured=500000.0,
        last_claim_status="Paid"
    )
    print(res3)
    assert "Risk Level: Fraudulent" in res3 or "Risk Level: High" in res3
    assert "Approved Amount: Rs. 0" in res3
    assert "Recommended Action: Reject" in res3
    print("Test 3: PASSED")

    # Test case 4: Non-medical reasons (groceries)
    print("\nTest 4: Non-medical reason (groceries)")
    res4 = verify_fraud_risk_tool(
        policy_commencement="2025-06-01",
        diagnosis="bought weekly groceries",
        claimed_amount=8000.0,
        sum_insured=500000.0,
        last_claim_status="Paid"
    )
    print(res4)
    assert "Risk Level: High" in res4
    assert "not a valid medical reason" in res4
    assert "Approved Amount: Rs. 0" in res4
    assert "Recommended Action: Reject" in res4
    print("Test 4: PASSED")

    # Test case 5: Unrecognized diagnosis (not matching standard medical list)
    print("\nTest 5: Unrecognized diagnosis")
    res5 = verify_fraud_risk_tool(
        policy_commencement="2025-06-01",
        diagnosis="some strange new word here",
        claimed_amount=15000.0,
        sum_insured=500000.0,
        last_claim_status="Paid"
    )
    print(res5)
    assert "Risk Level: High" in res5
    assert "unrecognized" in res5.lower() or "not standard" in res5.lower()
    assert "Approved Amount: Rs. 0" in res5
    assert "Recommended Action: Investigate" in res5
    print("Test 5: PASSED")

    # Test case 6: Invalid amount (<= 0)
    print("\nTest 6: Negative/zero amount")
    res6 = verify_fraud_risk_tool(
        policy_commencement="2025-06-01",
        diagnosis="Viral Fever",
        claimed_amount=-100.0,
        sum_insured=500000.0,
        last_claim_status="Paid"
    )
    print(res6)
    assert "Risk Level: High" in res6
    assert "invalid" in res6.lower()
    assert "Approved Amount: Rs. 0" in res6
    assert "Recommended Action: Reject" in res6
    print("Test 6: PASSED")

    print("\nAll verification tests completed successfully!")

if __name__ == "__main__":
    run_tests()
