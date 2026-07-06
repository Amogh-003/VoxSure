import os
import pypdf

dataset_dir = r"e:\amogh  visual studio\AI voice assistant\Dataset"
for name in ["HDFC-Life-Cancer-Care-FILLED-10-Holders.pdf", "HDFC-Life-Easy-Health-FILLED-10-Holders.pdf"]:
    path = os.path.join(dataset_dir, name)
    if os.path.exists(path):
        reader = pypdf.PdfReader(path)
        print(f"\n=== File: {name} (Pages: {len(reader.pages)}) ===")
        total_images = 0
        pages_with_images = []
        for i, page in enumerate(reader.pages):
            img_count = len(page.images)
            if img_count > 0:
                total_images += img_count
                pages_with_images.append(i + 1)
        print(f"Total images in PDF: {total_images}")
        if pages_with_images:
            print(f"Pages containing images: {pages_with_images[:20]} ...")
    else:
        print(f"File not found: {path}")
