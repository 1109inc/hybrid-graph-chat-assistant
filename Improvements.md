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

#### **Metrics / success criteria**

- **Cache hit rate (%)**
- **Reduction in embedding API calls**
- **Improved end-to-end latency** for repeated queries
- **Cache size and eviction stats** (optional future logging)

---
