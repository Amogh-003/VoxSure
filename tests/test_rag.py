import sys
import os

# Put parent directory in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge_base.retriever import retrieve_policy_context

queries = [
    "waiting period for cancer care",
    "revival rules for pension plan",
    "Silver plan benefits"
]

print("--- Testing RAG Multi-Document Retriever ---")
for q in queries:
    print(f"\nQuery: {repr(q)}")
    result = retrieve_policy_context(q)
    # Extract and print all [Source: ...] labels
    sources = []
    for line in result.split("\n"):
        if line.startswith("[Source:"):
            sources.append(line)
    print("Matched Sources:")
    for src in sources:
        print(f"  {src}")
