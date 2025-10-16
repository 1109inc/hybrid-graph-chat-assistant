# hybrid_chat.py
import json
from typing import List
from google import genai
import google.genai.types as genai_types 
from pinecone import Pinecone, ServerlessSpec
from neo4j import GraphDatabase
import config

# -----------------------------
# Config
# -----------------------------
EMBED_MODEL = "text-embedding-004"
CHAT_MODEL = "gemini-2.5-flash"
TOP_K = 5

INDEX_NAME = config.PINECONE_INDEX_NAME

# -----------------------------
# Initialize clients
# -----------------------------
# FIX 1: Explicitly pass the API key from config.py
client = genai.Client(api_key=config.GEMINI_API_KEY)

pc = Pinecone(api_key=config.PINECONE_API_KEY)

# Connect to Pinecone index
if INDEX_NAME not in pc.list_indexes().names():
    print(f"Creating managed index: {INDEX_NAME}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=config.PINECONE_VECTOR_DIM,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1") # FIX 2: Correct AWS region
    )

index = pc.Index(INDEX_NAME)

# Connect to Neo4j
driver = GraphDatabase.driver(
    config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
)

# -----------------------------
# Helper functions
# -----------------------------
def embed_text(text: str) -> List[float]:
    """Get embedding for a text string using Gemini API."""
    
    # FIX 3: contents must be a list of strings
    resp = client.models.embed_content(
        model=EMBED_MODEL,
        contents=[text], 
        # task_type must be in the config dictionary
        config={"task_type": "RETRIEVAL_QUERY"}
    )
    # FIX 4: Use dot notation to access the embedding values from the response object
    return resp.embeddings[0].values

def pinecone_query(query_text: str, top_k=TOP_K):
    """Query Pinecone index using embedding."""
    vec = embed_text(query_text)
    res = index.query(
        vector=vec,
        top_k=top_k,
        include_metadata=True,
        include_values=False
    )
    print("DEBUG: Pinecone top 5 results:")
    print(len(res["matches"]))
    return res["matches"]

def fetch_graph_context(node_ids: List[str], neighborhood_depth=1):
    """Fetch neighboring nodes from Neo4j."""
    facts = []
    with driver.session() as session:
        for nid in node_ids:
            q = (
                "MATCH (n:Entity {id:$nid})-[r]-(m:Entity) "
                "RETURN type(r) AS rel, labels(m) AS labels, m.id AS id, "
                # Ensure we retrieve all necessary data
                "m.name AS name, m.type AS type, m.description AS description "
                "LIMIT 10"
            )
            recs = session.run(q, nid=nid)
            for r in recs:
                # --- NEW LOGIC: Create a better name for the LLM to use ---
                target_desc = r["description"] or ""
                target_name = r["name"]
                
                # If the name is missing or generic, use the ID and part of the description
                if not target_name or len(target_name.strip()) < 3:
                    # Extracts the first 10 words or 50 characters of the description for the LLM
                    desc_snippet = " ".join(target_desc.split()[:10])
                    target_name = f"'{desc_snippet}' (ID:{r['id']})"
                
                # --------------------------------------------------------
                
                facts.append({
                    "source": nid,
                    "rel": r["rel"],
                    "target_id": r["id"],
                    "target_name": target_name, # Use the new, more descriptive name
                    "target_desc": target_desc[:400],
                    "labels": r["labels"]
                })
    print("DEBUG: Graph facts:")
    print(len(facts))
    return facts

def build_prompt(user_query, pinecone_matches, graph_facts):
    """Build a chat prompt combining vector DB matches and graph facts."""
    system = (
        "You are a travel itinerary assistant. **Use the names and descriptive text** provided in the context to form a natural-language itinerary. **NEVER** include the 'id', 'node id', or any code in your final response. Focus on giving the user the best 2-3 specific place names or descriptions per day."
    )

    vec_context = []
    for m in pinecone_matches:
        meta = m["metadata"]
        score = m.get("score", None)
        snippet = f"- id: {m['id']}, name: {meta.get('name','')}, type: {meta.get('type','')}, score: {score}"
        if meta.get("city"):
            snippet += f", city: {meta.get('city')}"
        vec_context.append(snippet)

    graph_context = [
        f"- ({f['source']}) -[{f['rel']}]-> ({f['target_id']}) {f['target_name']}: {f['target_desc']}"
        for f in graph_facts
    ]

    prompt = [
        {"role": "system", "content": system},
        {"role": "user", "content":
            f"User query: {user_query}\n\n"
            "Top semantic matches (from vector DB):\n" + "\n".join(vec_context[:10]) + "\n\n"
            "Graph facts (neighboring relations):\n" + "\n".join(graph_context[:20]) + "\n\n"
            "Based on the above, answer the user's question. If helpful, suggest 2–3 concrete itinerary steps or tips and mention node ids for references."}
    ]
    return prompt

def call_chat(prompt_messages):
    """Call Gemini ChatCompletion."""
    
    # 1. Extract the system instruction and the user message
    system_instruction = prompt_messages[0]["content"]
    user_content = prompt_messages[1]["content"]

    # 2. Configure the generation parameters
    config = genai_types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2
    )

    # 3. Call the Gemini model. Pass only the user content.
    resp = client.models.generate_content(
        model=CHAT_MODEL,
        contents=[user_content],
        config=config
    )
    
    # Return the text part of the response
    return resp.text

# -----------------------------
# Interactive chat
# -----------------------------
def interactive_chat():
    print("Hybrid travel assistant. Type 'exit' to quit.")
    while True:
        query = input("\nEnter your travel question: ").strip()
        if not query or query.lower() in ("exit","quit"):
            break

        matches = pinecone_query(query, top_k=TOP_K)
        match_ids = [m["id"] for m in matches]
        graph_facts = fetch_graph_context(match_ids)
        prompt = build_prompt(query, matches, graph_facts)
        answer = call_chat(prompt)
        print("\n=== Assistant Answer ===\n")
        print(answer)
        print("\n=== End ===\n")

if __name__ == "__main__":
    interactive_chat()