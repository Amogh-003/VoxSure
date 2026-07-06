import os
import json
import math
import re
import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Simple list of English stopwords to filter out common words
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "arent", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can", "cant", "cannot", "could", "couldnt",
    "did", "didnt", "do", "does", "doesnt", "doing", "dont", "down", "during",
    "each",
    "few", "for", "from", "further",
    "had", "hadnt", "has", "hasnt", "have", "havent", "having", "he", "hed", "hell", "hes", "her", "here", "heres",
    "hers", "herself", "him", "himself", "his", "how", "hows",
    "i", "id", "ill", "im", "ive", "if", "in", "into", "is", "isnt", "it", "its", "itself",
    "lets", "me", "more", "most", "mustnt", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shant", "she", "shed", "shell", "shes", "should", "shouldnt", "so", "some", "such",
    "than", "that", "thats", "the", "their", "theirs", "them", "themselves", "then", "there", "theres", "these",
    "they", "theyd", "theyll", "theyre", "theyve", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasnt", "we", "wed", "well", "were", "weve", "werent", "what", "whats", "when", "whens",
    "where", "wheres", "which", "while", "who", "whos", "whom", "why", "whys", "with", "wont", "would", "wouldnt",
    "you", "youd", "youll", "youre", "youve", "your", "yours", "yourself", "yourselves"
}

class GeminiEmbeddingFunction(EmbeddingFunction):
    """
    Custom Chroma Embedding Function that batches text embedding requests 
    using the Gemini API (text-embedding-004).
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Delay initialization of genai Client to ensure API key is available
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        chunk_size = 50  # Batch size to limit payload size
        for i in range(0, len(input), chunk_size):
            batch = input[i:i+chunk_size]
            try:
                # Use Gemini gemini-embedding-001 model
                response = self.client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=batch
                )
                for emb in response.embeddings:
                    embeddings.append(emb.values)
            except Exception as e:
                print(f"WARNING: Gemini embedding request failed: {e}. Falling back to zero-embeddings.")
                for _ in batch:
                    embeddings.append([0.0] * 768)
        return embeddings

class PolicyRetriever:
    def __init__(self):
        self.chunks_path = r"e:\amogh  visual studio\AI voice assistant\knowledge_base\policy_chunks.json"
        self.chroma_path = r"e:\amogh  visual studio\AI voice assistant\knowledge_base\chroma_db"
        self.chunks = []
        self.doc_frequencies = {}
        self.num_docs = 0
        
        # Load JSON chunks first (for initialization and backup TF-IDF search)
        self._load_and_initialize_tfidf()
        
        # Initialize Chroma DB vector store
        self._initialize_chroma()
        
    def _tokenize(self, text: str) -> list[str]:
        words = re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())
        return [w for w in words if w not in STOPWORDS]

    def _load_and_initialize_tfidf(self):
        if not os.path.exists(self.chunks_path):
            print(f"WARNING: Policy chunks file not found at {self.chunks_path}.")
            return
            
        with open(self.chunks_path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)
            
        self.num_docs = len(self.chunks)
        
        for chunk in self.chunks:
            tokens = set(self._tokenize(chunk["text"]))
            for token in tokens:
                self.doc_frequencies[token] = self.doc_frequencies.get(token, 0) + 1

    def _initialize_chroma(self):
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                print("WARNING: GEMINI_API_KEY not found in environment. Chroma vector DB will run in fallback mode.")
                
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            self.emb_fn = GeminiEmbeddingFunction(api_key)
            
            self.collection = self.chroma_client.get_or_create_collection(
                name="policy_documents",
                embedding_function=self.emb_fn
            )
            
            # If the collection is empty, populate it with our text chunks
            if self.collection.count() == 0 and self.chunks:
                print(f"Populating Chroma DB collection '{self.collection.name}' with policy chunks...")
                ids = [f"chunk_{idx}" for idx in range(len(self.chunks))]
                documents = [chunk["text"] for chunk in self.chunks]
                metadatas = [{"source": chunk["source"], "page": chunk["page"]} for chunk in self.chunks]
                
                # Insert in batches of 100 to stay under rate limits
                batch_size = 100
                for idx in range(0, len(self.chunks), batch_size):
                    self.collection.add(
                        ids=ids[idx:idx+batch_size],
                        documents=documents[idx:idx+batch_size],
                        metadatas=metadatas[idx:idx+batch_size]
                    )
                print(f"Successfully loaded {self.collection.count()} chunks into Chroma DB.")
        except Exception as e:
            print(f"WARNING: Failed to initialize Chroma DB: {e}. System will run on TF-IDF fallback.")
            self.collection = None

    def _search_tfidf(self, query: str, top_k_per_doc: int = 2) -> list[dict]:
        query_tokens = self._tokenize(query)
        if not query_tokens or not self.chunks:
            return []
            
        chunks_by_source = {}
        for chunk in self.chunks:
            source = chunk["source"]
            if source not in chunks_by_source:
                chunks_by_source[source] = []
            chunks_by_source[source].append(chunk)
            
        aggregated_results = []
        for source, doc_chunks in chunks_by_source.items():
            scored_doc_chunks = []
            for chunk in doc_chunks:
                chunk_tokens = self._tokenize(chunk["text"])
                if not chunk_tokens:
                    continue
                    
                score = 0.0
                for token in query_tokens:
                    if token in chunk_tokens:
                        tf = chunk_tokens.count(token) / len(chunk_tokens)
                        df = self.doc_frequencies.get(token, 0)
                        idf = math.log(1.0 + (self.num_docs - df + 0.5) / (df + 0.5))
                        score += tf * idf
                        
                if score > 0.0:
                    scored_doc_chunks.append((score, chunk))
                    
            scored_doc_chunks.sort(key=lambda x: x[0], reverse=True)
            for _, chunk in scored_doc_chunks[:top_k_per_doc]:
                aggregated_results.append(chunk)
                
        return aggregated_results

    def search_all_documents(self, query: str, top_k_per_doc: int = 2) -> list[dict]:
        """
        Queries keyword TF-IDF search first for maximum precision. If no direct keywords 
        match, queries Chroma DB for semantic vector similarity.
        """
        # 1. Try highly precise TF-IDF search first
        try:
            tfidf_results = self._search_tfidf(query, top_k_per_doc)
            if tfidf_results:
                return tfidf_results
        except Exception as e:
            print(f"TF-IDF search failed: {e}")

        # 2. Fallback to Chroma vector search
        if self.collection is not None:
            try:
                n_results = min(top_k_per_doc * 4, self.num_docs)
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results
                )
                
                formatted = []
                if results and results.get("documents") and results["documents"][0]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0]
                    for doc, meta in zip(docs, metas):
                        formatted.append({
                            "text": doc,
                            "source": meta["source"],
                            "page": meta["page"]
                        })
                    return formatted
            except Exception as e:
                print(f"Chroma DB query failed ({e}).")
                
        return []

# Global retriever instance
_retriever_instance = None

def get_retriever():
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = PolicyRetriever()
    return _retriever_instance

def retrieve_policy_context(query: str) -> str:
    """
    Retrieves relevant policy clauses and terms from the HDFC Annuity, Pension, Cancer Care, or Easy Health PDFs.
    """
    try:
        retriever = get_retriever()
        results = retriever.search_all_documents(query, top_k_per_doc=2)
        
        context_blocks = []
        
        # Look up active user index if running in Streamlit session
        import sys
        active_phone = None
        if "streamlit" in sys.modules:
            import streamlit as st
            try:
                active_phone = st.session_state.get("active_phone")
            except Exception:
                pass
                
        if active_phone:
            user_index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_indexes", f"{active_phone}.json")
            if os.path.exists(user_index_path):
                try:
                    with open(user_index_path, "r", encoding="utf-8") as f:
                        u_idx = json.load(f)
                    policies_str = json.dumps(u_idx.get("existing_policies", []), indent=2)
                    user_context = f"""[Active Caller Policy Profile - Structural Index]
Name: {u_idx.get('name')}
Phone: {u_idx.get('phone_number')}
Age: {u_idx.get('age')}
Income Bracket: {u_idx.get('income_bracket')}
Family Size: {u_idx.get('family_size')}
Last Claim Date: {u_idx.get('last_claim_date')}
Last Claim Status: {u_idx.get('last_claim_status')}
Renewal Due Date: {u_idx.get('renewal_due_date')}
Existing Policies details:
{policies_str}"""
                    context_blocks.append(user_context)
                except Exception as e:
                    print(f"Error loading user index context: {e}")
                    
        for res in results:
            context_blocks.append(
                f"[Source: {res['source']}, Page: {res['page']}]\n{res['text'].strip()}"
            )
            
        if not context_blocks:
            return "No matching clauses found in the database. Please request details from the advisor."
            
        return "\n\n---\n\n".join(context_blocks)
    except Exception as e:
        return f"Error retrieving policy context: {e}"
