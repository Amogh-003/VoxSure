import os
import pypdf

dataset_dir = r"e:\amogh  visual studio\AI voice assistant\Dataset"
for name in ["HDFC-Life-Cancer-Care-FILLED-10-Holders.pdf", "HDFC-Life-Easy-Health-FILLED-10-Holders.pdf"]:
    path = os.path.join(dataset_dir, name)
    if os.path.exists(path):
        reader = pypdf.PdfReader(path)
        print(f"\n=== File: {name} ===")
        fields = reader.get_fields()
        if fields:
            print(f"Found {len(fields)} fields.")
            # Print a few fields to inspect
            count = 0
            for field_name, field_val in fields.items():
                print(f"  Field: {field_name} = {field_val.get('/V')}")
                count += 1
                if count >= 15:
                    break
        else:
            print("No interactive fields found.")
            
            # Let's inspect annotations if any
            annot_count = 0
            for page_idx, page in enumerate(reader.pages):
                if "/Annots" in page:
                    annots = page["/Annots"]
                    print(f"  Page {page_idx+1} has {len(annots)} annotations.")
                    annot_count += len(annots)
                    if annot_count >= 10:
                        break
            if annot_count == 0:
                print("No annotations found either.")
    else:
        print(f"File not found: {path}")
