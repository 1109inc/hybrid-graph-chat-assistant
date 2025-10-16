import json
import time
from tqdm import tqdm
from google import genai
from pinecone import Pinecone, ServerlessSpec
import config

# -----------------------------
# Config (Updated for Gemini)
# -----------------------------
DATA_FILE = "vietnam_travel_dataset.json"
BATCH_SIZE = 32

INDEX_NAME = config.PINECONE_INDEX_NAME
# Set the model name for the Gemini embedding model
EMBED_MODEL = "text-embedding-004" 
# Vector dimension for text-embedding-004 is 768. 
VECTOR_DIM = 768 

# -----------------------------
# Initialize clients (Updated for Gemini)
# -----------------------------
# FIX: Explicitly pass the API key from config.py
client = genai.Client(api_key=config.GEMINI_API_KEY) 
pc = Pinecone(api_key=config.PINECONE_API_KEY)

# -----------------------------
# Create managed index if it doesn't exist (Already Correct)
# -----------------------------
existing_indexes = pc.list_indexes().names()
if INDEX_NAME not in existing_indexes:
    print(f"Creating managed index: {INDEX_NAME} with dimension {VECTOR_DIM}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=VECTOR_DIM, 
        metric="cosine",
        spec=ServerlessSpec(
            # FIX: Change cloud provider to AWS
            cloud="aws",
            # FIX: Change region to the supported AWS region for the free tier
            region="us-east-1"
        )
    )
else:
    print(f"Index {INDEX_NAME} already exists.")

# Connect to the index
index = pc.Index(INDEX_NAME)

# -----------------------------
# Helper functions (Updated and FIXED for Gemini)
# -----------------------------
def get_embeddings(texts: list, model: str) -> list[list[float]]:
    """Generate embeddings using the Gemini API."""
    
    # FIX 1: Change 'content' to 'contents' (plural)
    # FIX 2: Pass 'task_type' inside the 'config' dictionary
    resp = client.models.embed_content(
        model=model,
        contents=texts,
        config={"task_type": "RETRIEVAL_DOCUMENT"} 
    )
    
    # FIX 3: The response is an object, not a dict. 
    # Extract the vector list from each embedding object using dot notation.
    # The final output should be a list of lists of floats.
    return [e.values for e in resp.embeddings]

def chunked(iterable, n):
    for i in range(0, len(iterable), n):
        yield iterable[i:i+n]

# -----------------------------
# Main upload
# -----------------------------
def main():
    # Sanity check for correct dimension
    if config.PINECONE_VECTOR_DIM != VECTOR_DIM:
        print(f"WARNING: config.PINECONE_VECTOR_DIM is set to {config.PINECONE_VECTOR_DIM} but Gemini model '{EMBED_MODEL}' uses dimension {VECTOR_DIM}. Please update your config.py!")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        nodes = json.load(f)

    items = []
    for node in nodes:
        semantic_text = node.get("semantic_text") or (node.get("description") or "")[:1000]
        if not semantic_text.strip():
            continue
        meta = {
            "id": node.get("id"),
            "type": node.get("type"),
            "name": node.get("name"),
            "city": node.get("city", node.get("region", "")),
            "tags": node.get("tags", [])
        }
        items.append((node["id"], semantic_text, meta))

    print(f"Preparing to upsert {len(items)} items to Pinecone using {EMBED_MODEL}...")

    for batch in tqdm(list(chunked(items, BATCH_SIZE)), desc="Uploading batches"):
        ids = [item[0] for item in batch]
        texts = [item[1] for item in batch]
        metas = [item[2] for item in batch]

        # Call the corrected helper function
        embeddings = get_embeddings(texts, model=EMBED_MODEL)

        vectors = [
            {"id": _id, "values": emb, "metadata": meta}
            for _id, emb, meta in zip(ids, embeddings, metas)
        ]

        index.upsert(vectors)
        time.sleep(0.2)

    print("All items uploaded successfully.")

# -----------------------------
if __name__ == "__main__":
    main()