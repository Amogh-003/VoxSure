import os
import pypdf
import re

dataset_dir = r"e:\amogh  visual studio\AI voice assistant\Dataset"
for name in ["HDFC-Life-Cancer-Care-FILLED-10-Holders.pdf", "HDFC-Life-Easy-Health-FILLED-10-Holders.pdf"]:
    path = os.path.join(dataset_dir, name)
    if os.path.exists(path):
        reader = pypdf.PdfReader(path)
        print(f"\n=== File: {name} ===")
        
        # Scan each page
        for page_idx, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text:
                continue
                
            # Search for "Dear " and check what follows
            matches = re.findall(r"Dear\s+([^,\n\r\t]+),?", text)
            for match in matches:
                clean_match = match.strip()
                if "<<" not in clean_match and "Policyholder" not in clean_match:
                    print(f"Page {page_idx+1}: Found Dear match: '{clean_match}'")
                    
            # Let's search for "Policy no." or "Policy number" and check what follows
            policy_matches = re.findall(r"Policy\s+no(?:m|.|)\s*[:.\s]*([^<\n\r\t]+)", text, re.IGNORECASE)
            for pm in policy_matches:
                clean_pm = pm.strip()
                if clean_pm and "<<" not in clean_pm and len(clean_pm) > 2 and re.search(r'\w', clean_pm):
                    # Only print if it looks like a real value
                    print(f"Page {page_idx+1}: Found potential Policy no: '{clean_pm}'")
    else:
        print(f"File not found: {path}")
