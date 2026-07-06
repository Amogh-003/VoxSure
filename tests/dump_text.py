import os
import pypdf

dataset_dir = r"e:\amogh  visual studio\AI voice assistant\Dataset"
for name in ["HDFC-Life-Cancer-Care-FILLED-10-Holders.pdf", "HDFC-Life-Easy-Health-FILLED-10-Holders.pdf"]:
    path = os.path.join(dataset_dir, name)
    if os.path.exists(path):
        reader = pypdf.PdfReader(path)
        print(f"\n=== File: {name} (Pages: {len(reader.pages)}) ===")
        # Check first 5 pages for any actual text containing names or content
        for i in range(min(15, len(reader.pages))):
            text = reader.pages[i].extract_text()
            if not text:
                continue
            # Search for typical name patterns or "Dear"
            if "dear" in text.lower() or "holder" in text.lower() or "policy" in text.lower():
                print(f"Page {i+1} preview:")
                lines = [l.strip() for l in text.split('\n') if l.strip()][:10]
                for l in lines:
                    print("  ", l)
    else:
        print(f"File not found: {path}")
