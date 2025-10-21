### **Embedding Cache (SQLite) — Design Overview and Trade-offs**

Added **persistent, local SQLite-based embedding cache** designed for efficient reuse of text embeddings (e.g., from Gemini or OpenAI models).
Each embedding is stored as a **compact binary float32 blob**, uniquely keyed by a **SHA-256 hash** of the `(model + normalized_text)` combination.

The cache now supports:

- **Batch lookups** (`batch_get_embeddings`) for efficient retrieval with large input lists.
- **TTL-based expiration** (default 30 days) to keep embeddings fresh.
- **Automatic eviction** of the oldest entries once the cache exceeds a configured size cap.
- **Graceful expiration cleanup** during both single and batch retrieval.
- **Compact, consistent key normalization** to ensure semantically identical text yields the same cache key.

---

#### **Why SQLite**

- **Persistent and portable** — survives restarts and requires no external service.
- **Space-efficient** — embeddings stored as raw binary float32 arrays minimize disk use.
- **Concurrency-friendly** — supports multiple concurrent reads; serialized writes are acceptable for single-machine demo use.
- **Zero setup** — no dependencies beyond Python’s standard library and NumPy.

SQLite is ideal for **single-host prototypes, research notebooks, or internship demos** where reproducibility, simplicity, and persistence matter more than high throughput.

---

#### **Design trade-offs**

| Option                  | Pros                                  | Cons                                               |
| ----------------------- | ------------------------------------- | -------------------------------------------------- |
| **In-memory dict**      | Fastest lookups                       | Ephemeral; lost on restart                         |
| **JSON / pickle files** | Simple to implement                   | Inefficient for large arrays; not concurrency-safe |
| **Redis**               | Fast, scalable, native TTL            | Requires external infrastructure                   |
| **LMDB / RocksDB**      | High-performance for massive datasets | More complex setup and tuning                      |
| **SQLite (chosen)**     | Persistent, lightweight, reliable     | Moderate write contention under heavy parallel use |

SQLite provides the **best balance** of performance, reliability, and zero-maintenance setup for local demos and single-machine applications.

---

#### **Scalability path**

For production or distributed use:

- Migrate to **Redis** or a **managed cache** (e.g., AWS ElastiCache, GCP Memorystore).
- Store embeddings as binary values or base64-encoded blobs.
- Leverage built-in TTL and LRU eviction.
- Migration is seamless — cache keys remain stable (`sha256(model + normalized_text)`).

---

![Cache_improvement](https://i.ibb.co/RTnZRq8L/cache-improvement.png)

#### Embedding cache reduces repeated upsert/load time by 57%, demonstrating tangible performance improvement.

---

### **Prompt clarity & inferred-name behavior**

Improved the system prompt used by the chat model so the assistant will infer **human-readable place names** from node descriptions when a node’s name field is missing or unhelpful. This fixed the prior behavior where the assistant would output internal node IDs like **Da Lat Attraction 251**, and replaced it with readable names such as **Lang Biang Mountain (inferred)**.

---

#### **Why**

- The original prompt allowed the model to reuse raw node identifiers (IDs) in answers, which is unreadable to end users.

- Missing name metadata is common in scraped or minimal datasets; having the model infer reasonable names improves user experience without changing source data.

- This is a low-effort, high-impact improvement for demo/testing: no data reprocessing required.

---

### **Before improvement**

![Before](https://i.ibb.co/9HZknZxd/before-prompt-improv.png)

### **After improvement**

![After](https://i.ibb.co/svR8pRhF/after-prompt-improv.png)

#### The output after improvement is readable and transparent, as users can see when a place name was inferred from its description, which also helps in testing and debugging.

---

### **Async Neo4j Graph Fetch — Design Overview and Trade-offs**

#### **What it does**

- Parallelizes per-node Neo4j lookups by running the existing per-node Cypher query in worker threads (asyncio.to_thread) and gathering results concurrently with asyncio.gather.
- Returns the same structured facts used by the prompt builder: source, rel, target_id, target_name, target_desc, labels.
- Includes a bounded Semaphore to avoid overwhelming the DB and a warmup recommendation to avoid first-run spikes.

---

#### **Design trade-offs (two approaches)**

| Approach                                 |                                                                                                                                                               Pros | Cons                                                                                                                                                                |
| ---------------------------------------- | -----------------------------------------------------------------------------------------------------------------------------------------------------------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| asyncio.to_thread per-node (current)     | - Minimal code change; reuses existing Neo4j driver and queries. <br>- Easy to test, debug and roll back. <br>- Good latency win for moderate fanout (≈10–30 ids). | - Still multiple DB round-trips (one per id). <br>- Thread/connection overhead increases with large node counts.                                                    |
| Single-request UNWIND via HTTP (aiohttp) |                                          - Single network round-trip for many ids; best latency for large batches. <br>- Lower overall overhead for hundreds+ ids. | - Requires HTTP transactional endpoint and Basic auth handling. <br>- More JSON parsing and error/response-shape handling. <br>- Larger code & operational changes. |

---

#### **Why we chose the asyncio.to_thread approach**

Based on the trade-off table above, asyncio.to_thread wins for our current needs because it delivers a large portion of the practical latency improvement with minimal engineering risk. It reuses the existing driver and query logic (no new endpoints or auth), is easy to instrument, and is the best fit for the observed workload (≈12–30 node lookups per query). The UNWIND/aiohttp approach is better only when node counts are much larger and the extra implementation complexity and HTTP handling are justified.

---

#### **Scalability path**

- Short term: use asyncio.to_thread with a bounded Semaphore (e.g., min(16, len(ids))) and a one-time warmup to remove cold-start overhead. Measure and report mean/median over multiple runs.
- Mid term: make embeddings and cache access non-blocking (async wrappers or aiosqlite / to_thread) to create a fully async pipeline.
- Long term: switch to UNWIND/batch via Neo4j HTTP transactional endpoint (aiohttp) for high-throughput cases (hundreds+ ids), and/or move cache to Redis for distributed scale.

---

#### **Features**

- Time distribution shown: CLI prints a per-query timing breakdown (Pinecone embed+query, graph fetch, model generation, total), enabling analysis of where time is spent and validating async gains.
- Warmup to ignore startup overhead: the interactive flow performs a light async warmup (one dummy fetch) so first-run connection and pool setup do not skew timing measurements.

---

### **Before async**

![Before](https://i.ibb.co/SD2zYnzY/before-async.png)

### **After async**

![After](https://i.ibb.co/67mB44ZK/after-async.png)

#### Async implementation cut graph fetching time by ~94.3%, highlighting a significant performance boost.
