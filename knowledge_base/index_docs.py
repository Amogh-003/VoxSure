import os
import json
from pypdf import PdfReader

def extract_and_chunk_pdfs():
    dataset_dir = r"e:\amogh  visual studio\AI voice assistant\Dataset"
    output_path = r"e:\amogh  visual studio\AI voice assistant\knowledge_base\policy_chunks.json"
    
    chunks = []
    chunk_id = 0
    
    # Target chunking configuration
    chunk_size = 1000
    chunk_overlap = 200
    
    print("Starting extraction of PDFs...")
    
    for filename in os.listdir(dataset_dir):
        if not filename.endswith(".pdf"):
            continue
            
        filepath = os.path.join(dataset_dir, filename)
        print(f"Processing: {filename}")
        
        try:
            reader = PdfReader(filepath)
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if not text or not text.strip():
                    continue
                    
                # Clean simple whitespace
                cleaned_text = " ".join(text.split())
                
                # Dynamic sliding-window chunker
                start = 0
                while start < len(cleaned_text):
                    end = start + chunk_size
                    chunk_text = cleaned_text[start:end]
                    
                    chunks.append({
                        "id": f"chunk_{chunk_id}",
                        "source": filename,
                        "page": page_idx + 1,
                        "text": chunk_text
                    })
                    
                    chunk_id += 1
                    
                    # Advance window by size minus overlap
                    if end >= len(cleaned_text):
                        break
                    start += (chunk_size - chunk_overlap)
                    
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            
    # Save serialized chunks to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
        
    print(f"\nCompleted! Generated {len(chunks)} text chunks and saved to {output_path}")

if __name__ == "__main__":
    extract_and_chunk_pdfs()
