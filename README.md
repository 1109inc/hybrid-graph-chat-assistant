# Hybrid Chat Travel Assistant — Project Documentation

## Overview

This project implements a **Hybrid Chat-based Travel Assistant** that combines:

- **Google Gemini (Generative AI)** for natural language reasoning and embeddings.
- **Pinecone Vector Database** for semantic search and similarity retrieval.
- **Neo4j Graph Database** for relational knowledge and graph-based reasoning.

The assistant can answer complex travel-related queries using both semantic and graph contexts, generating well-structured, grounded answers.

---

## ⚙️ Environment Setup

### 1. Python Environment

Use **Python 3.11** — this version ensures full Neo4j driver compatibility.

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate   # On Windows
```

### 2. Install Dependencies

Create a `requirements.txt` with:

```
neo4j==5.9.0
#openai==1.0.0
pyvis==0.3.1
networkx==3.1
tqdm
python-dotenv
google-genai
```

Then install:

```bash
pip install -r requirements.txt
```

---

## 🔑 Configuration (`config.py`)

Create a file named `config.py` and add your credentials:

```python
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

GEMINI_API_KEY = "<YOUR_GEMINI_KEY>"
PINECONE_API_KEY = "<YOUR_PINECONE_KEY>"
PINECONE_ENV = "us-east1-gcp"
PINECONE_INDEX_NAME = "vietnam-travel"
PINECONE_VECTOR_DIM = 768 # Depending upon embedding model
```

> 🧠 Note: We replaced the OpenAI API with **Google Gemini**, using `text-embedding-004` for embeddings and `gemini-2.5-flash` for chat responses.

---

## 🧩 Pipeline Breakdown

### Step 1: Data Upload to Pinecone (`pinecone_upload.py`)

- Embeds each travel node using **Gemini’s text-embedding-004** (dimension 768).
- Automatically creates a **Pinecone managed index** using AWS `us-east-1` for free-tier compatibility.
- Uploads the embedded data in batches of 32.

**Run:**

```bash
python pinecone_upload.py
```

✅ Example Output:

```
Creating managed index: vietnam-travel with dimension 768
Preparing to upsert 360 items...
Uploading batches: 100%|██████████████████| 12/12 [00:26<00:00,  2.18s/it]
All items uploaded successfully.
```

## Index details

![Index](https://i.ibb.co/1tFmBwp8/index-details.png)

## Upsert Batch

![Upsertbatch](https://i.ibb.co/GQg0tW8c/upsert-batch.png)

### Step 2: Load Data into Neo4j (`load_to_neo4j.py`)

This loads the dataset into Neo4j, creating nodes and relationships.

**Run:**

```bash
python load_to_neo4j.py
```

✅ Creates:

- `Entity` label for all nodes.
- Relationships like `LOCATED_IN`, `RELATED_TO`, etc.

---

### Step 3: Visualize Graph (`visualization_graph.py`)

Generates an interactive graph of your Neo4j data using **PyVis**.

**Run:**

```bash
python visualization_graph.py
```

✅ Output:

```
Saved visualization to neo4j_viz.html
```

Open the file in your browser to confirm graph connectivity.

## Visualization Graph

<img width="1895" height="893" alt="neo4j-viz-img_full_size" src="https://github.com/user-attachments/assets/2c475bca-d3a2-4574-9be5-be104f6c791c" />


### Step 4: Hybrid Chat Assistant (`hybrid_chat.py`)

This integrates:

- Gemini’s **embeddings** for semantic understanding.
- Pinecone’s **vector search** for retrieving relevant nodes.
- Neo4j’s **graph context** for connected entity facts.

**Run the interactive CLI:**

```bash
python hybrid_chat.py
```

You’ll see:

```
Hybrid travel assistant. Type 'exit' to quit.
Enter your travel question:
```

Then you can type queries like:

#### 🧭 Information Retrieval

> "What is the most romantic spot in Hoi An, and where is it located?"

#### 🌸 Entity Group Queries

> "Tell me about the flower gardens in Da Lat. What kind of experience do they offer?"

#### 🏔️ Complex Relationship Queries

> "If I want a scenic mountain view in Da Lat, what specific attraction should I visit, and what is its most appealing feature for couples?"

#### ⚖️ Comparative Queries

> "Compare the atmosphere of Hoi An with Da Lat. Which city is better for a honeymoon retreat, and why?"

The assistant will use **Pinecone’s semantic matches** and **Neo4j’s graph relationships** to craft coherent, grounded answers.

## Interactive CLI

![CLI](https://i.ibb.co/RG4yr1gL/hybrid-chat-CLI.png)

---

## 🧠 Improvements Implemented

| Component       | Change                             | Reason                                    |
| --------------- | ---------------------------------- | ----------------------------------------- |
| Python version  | Downgraded to 3.11                 | Neo4j compatibility                       |
| API             | Switched from OpenAI → Gemini      | Free & robust embeddings/chat             |
| Pinecone setup  | Auto-creates AWS `us-east-1` index | Free tier support                         |
| Embedding model | `text-embedding-004` (768-dim)     | Faster + free tier                        |
| Chat model      | `gemini-2.5-flash`                 | Optimized for reasoning & travel queries  |
| Prompt          | Redesigned system prompt           | Ensures grounded, itinerary-style answers |

---

### 📁 Folder structure

```
HYBRID_CHAT_TEST/
│
├── README.md
├── requirements.txt
├── load_to_neo4j.py
├── hybrid_chat.py
├── pinecone_upload.py
├── visualize_graph.py
├── .gitignore

```

---

### Branches Overview

- **main** → baseline working submission.
- **improvements** → extended version with caching and other enhancements.

---

## 🧭 Example Flow Summary

1. Setup Python 3.11 environment & install dependencies
2. Add credentials in `config.py`
3. Run `pinecone_upload.py` → verify upload in Pinecone
4. Run `load_to_neo4j.py` → verify in Neo4j
5. Run `visualization_graph.py` → open `neo4j_viz.html`
6. Run `hybrid_chat.py` → chat interactively

✅ Result: A **hybrid AI travel assistant** that retrieves, reasons, and generates grounded responses using both vector and graph data.
