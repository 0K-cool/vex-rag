# Vex RAG Plugin 🦖⚡

> 100% local RAG system with hybrid search, contextual chunking, and BGE reranking

**Version:** 1.1.0
**Author:** Kelvin Lomboy
**License:** MIT

---

## What is Vex RAG?

A production-ready Retrieval-Augmented Generation (RAG) system designed for **100% local processing** with zero cloud APIs and zero cost. Distributed as a Python library with MCP server integration and CLI tools for seamless integration with Claude Code.

### Key Features

- ✅ **Contextual chunking** - Llama 3.1 8B for boundary-aware document segmentation
- ✅ **Vector search** - nomic-embed-text (768-dim) for semantic similarity
- ✅ **BM25 keyword search** - LanceDB FTS for exact keyword matching
- ✅ **Reciprocal Rank Fusion** - Combines vector + BM25 rankings
- ✅ **BGE reranking** - Local reranking (Apple Silicon GPU optimized)
- ✅ **MCP server integration** - Automatic context injection into conversations
- ✅ **Multi-project support** - Portable across projects via configuration
- ✅ **PII sanitization** - Multi-layer sanitization (configurable)
- ✅ **Auto-indexing** - Git post-commit hooks (optional, manual setup)
- ✅ **Native citations** - Anthropic citations API support

---

## Installation

### Prerequisites

- **Python 3.11+** (tested on 3.13)
- **Ollama** installed and running
- **Claude Code CLI** (latest version)

### 1. Clone Repository

```bash
# Clone to tools directory
cd ~/tools
git clone https://github.com/0K-cool/vex-rag.git
cd vex-rag
```

### 2. Install Python Package

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install vex-rag package (editable mode)
pip install -e .

# Install spaCy model for PII detection
python -m spacy download en_core_web_sm
```

**What Gets Installed:**
- ✅ Python `rag` module (importable library)
- ✅ CLI tools: `vex-search`, `vex-index` (added to PATH)
- ✅ MCP server: `mcp_server/vex_kb_server.py`
- ✅ All dependencies from `pyproject.toml`

### 3. Pull Required Ollama Models

```bash
# Context generation model
ollama pull llama3.1:8b

# Embedding model
ollama pull nomic-embed-text
```

### 4. Configure Your Project

```bash
# Navigate to your project
cd ~/your-project

# Copy example configuration
cp ~/tools/vex-rag/examples/config.pai.yml .vex-rag.yml

# Edit configuration for your project
# At minimum: update project.name and security.allowed_base_paths
vim .vex-rag.yml
```

### 5. Initialize Database

```bash
# Create empty LanceDB database
mkdir -p lance_kb

# Index your first documents
vex-index docs/ --batch
```

### 6. Setup MCP Server

**CRITICAL:** Add the MCP server configuration to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "vex-knowledge-base": {
      "command": "/Users/yourusername/tools/vex-rag/.venv/bin/python3",
      "args": [
        "/Users/yourusername/tools/vex-rag/mcp_server/vex_kb_server.py"
      ],
      "env": {
        "RAG_CONFIG": "/Users/yourusername/your-project/.vex-rag.yml",
        "PYTHONPATH": "/Users/yourusername/tools/vex-rag"
      },
      "description": "Vex RAG Plugin - Automatic context injection from knowledge base"
    }
  }
}
```

**Important Notes:**
- Replace `/Users/yourusername/` with your actual paths
- `PYTHONPATH` is **REQUIRED** - without it, Python can't find the `rag` module
- `RAG_CONFIG` should point to your project's `.vex-rag.yml` file
- Restart Claude Code after adding this configuration

**Troubleshooting:**
- If MCP server doesn't connect: Check that `PYTHONPATH` points to the vex-rag directory
- If you get "module not found" errors: Verify `PYTHONPATH` is set in `.mcp.json`
- Logs location: Configured in `.vex-rag.yml` under `logging.file`

### ✅ Installation Complete!

After completing these steps, you have:

**CLI Tools:**
```bash
vex-search "your query here"              # Search knowledge base
vex-index document.md --project MyProject # Index documents
```

**MCP Server:**
- Automatic context injection in Claude Code conversations
- Use `vex://search/{query}` resource or ask questions naturally
- Tools: `index_document`, `get_kb_stats`

**Python Library:**
```python
from rag.indexing import KnowledgeBaseIndexer
from rag.retrieval import RetrievalPipeline
# Use in your own Python scripts
```

**Next Steps:**
1. Start Claude Code in your project directory
2. Verify MCP server loads (check session banner)
3. Ask Claude: "Search the knowledge base for X"
4. Index more documents as needed

---

## Configuration

Create `.vex-rag.yml` in your project root:

```yaml
project:
  name: MyProject
  description: My knowledge base

database:
  path: ./lance_kb
  backup_dir: ~/backups/

indexing:
  chunk_size: 384
  chunk_overlap: 0.15
  context_model: llama3.1:8b
  embedding_model: nomic-embed-text:latest
  enable_sanitization: true
  auto_index_extensions:
    - .md
    - .pdf
    - .txt
  auto_index_paths:
    - docs/
    - README.md

retrieval:
  default_top_k: 5
  vector_limit: 20
  bm25_limit: 20
  fusion_limit: 10
  enable_reranking: true
  reranker_model: BAAI/bge-reranker-large

projects_to_index:
  - name: MyProject
    paths:
      - docs/
      - README.md

security:
  # Allowed base directories for file operations (prevents path traversal)
  # All document paths must be within these directories
  allowed_base_paths:
    - ~/your-project
    - ~/other-allowed-directory

backup:
  enabled: true
  schedule: weekly
  retention:
    daily: 7
    weekly: 4

logging:
  level: INFO
  file: ./logs/rag.log
```

See `examples/` directory for project-specific configurations:
- `config.pai.yml` - Personal AI Infrastructure
- `config.ir.yml` - Incident Response platform
- `config.pentest.yml` - Penetration testing platform

---

## Usage

### Automatic Context Injection (MCP)

Once installed, the RAG system automatically provides context to Claude Code conversations:

```
User: "What are the git safety protocols?"
Claude: [Automatically searches knowledge base and provides answer with sources]
```

The MCP server runs transparently in the background. No manual search needed.

### CLI Tools

```bash
# Search from command line
vex-search "backup procedures" --top-k 10 --rerank

# Index from command line
vex-index document.pdf --project MyProject

# Batch index directory
vex-index --pattern 'docs/**/*.md'

# Dry run to preview
vex-index --pattern 'docs/**/*.pdf' --dry-run

# Get KB statistics
python -c "from rag import KnowledgeBaseIndexer; k=KnowledgeBaseIndexer('.vex-rag.yml'); print(k.get_stats())"
```

### MCP Tools (In Conversation)

```python
# Index a document
index_document(
    file_path="docs/new-doc.md",
    project="MyProject",  # Optional, uses config default
    enable_sanitization=True  # Optional, uses config default
)

# Get KB statistics
stats = get_kb_stats()
# Returns: {total_chunks, unique_projects, unique_files, storage_size}
```

### MCP Resources

```
# Search resource (automatic)
vex://search/{query}

# Example: vex://search/git%20safety%20protocols
```

---

## Indexing Pipeline

When you index a document, it goes through:

1. **Document Loading** - Parse file (MD, PDF, DOCX, PPTX, TXT)
2. **PII Sanitization** - Multi-layer redaction (if enabled)
3. **Contextual Chunking** - Boundary-aware segmentation (384 tokens, 15% overlap)
4. **Context Generation** - Llama 3.1 8B generates chunk summaries
5. **Embedding** - nomic-embed-text creates 768-dim vectors
6. **LanceDB Indexing** - Store chunks with vectors and metadata

**Performance:**
- ~1-2 seconds per chunk
- ~2-5 chunks per document (varies by length)
- 100% local processing (zero cloud APIs)

---

## Retrieval Pipeline

When you search, the system performs:

1. **Query Embedding** - Convert query to 768-dim vector (nomic-embed-text)
2. **Vector Search** - Semantic similarity search (top 20 results)
3. **BM25 Search** - Keyword matching search (top 20 results)
4. **Reciprocal Rank Fusion** - Combine rankings (top 10 fused results)
5. **BGE Reranking** - Final reranking for accuracy (top 5 results)

**Performance:**
- First search: ~6 seconds (BGE model load)
- Subsequent searches: ~2 seconds
- 100% local processing (Apple Silicon GPU for reranking)

---

## Auto-Indexing (Git Hook)

Automatically index modified files after git commits:

### Installation

```bash
# Copy hook to your project (if hook exists)
cp ~/tools/vex-rag/hooks/post-commit.sh .git/hooks/post-commit 2>/dev/null || \
  echo "Note: Hook not included in plugin. Create your own or see examples/"

# Make executable
chmod +x .git/hooks/post-commit
```

### Configuration

Edit `.vex-rag.yml`:

```yaml
indexing:
  auto_index_extensions:
    - .md
    - .pdf
  auto_index_paths:
    - docs/
    - playbooks/
    - README.md
```

Now, when you commit changes to matching files, they're automatically indexed.

---

## Supported File Formats

- **Markdown** (`.md`)
- **PDF** (`.pdf`)
- **Word Documents** (`.docx`)
- **PowerPoint** (`.pptx`)
- **Plain Text** (`.txt`)

---

## Security & Privacy

### 100% Local Processing

- **Embeddings:** Generated locally via Ollama (nomic-embed-text)
- **Context generation:** Local Llama 3.1 8B via Ollama
- **Reranking:** Local BGE model on Apple Silicon GPU
- **Search:** Local LanceDB vector database
- **Zero cloud APIs** - No data leaves your machine

### PII Sanitization

- **Multi-layer sanitization:** Regex patterns + NER (spaCy)
- **Configurable:** Enable/disable per project
- **Safe for client work:** Redacts emails, phone numbers, SSNs, API keys, etc.
- **Review flag:** Marks documents needing manual review

**Detected patterns:**
- Email addresses
- Phone numbers
- Social Security Numbers
- Credit card numbers
- API keys and tokens
- IP addresses
- Named entities (people, organizations, locations)

### Data Storage

- **LanceDB:** Local vector database (configurable location)
- **Backups:** Configurable location (encrypted if using Proton Drive)
- **Logs:** Configurable location
- **File permissions:** 600/700 (owner read/write only)

### Security Hardening (v1.0.1+)

**Protection Against Common Vulnerabilities:**

- **SQL Injection Prevention (VUL-001 Fixed):**
  - Input sanitization for all LanceDB queries
  - Single quote escaping following SQL standard (' → '')
  - 22 comprehensive security tests covering attack vectors
  - OWASP A05:2025 compliant

- **Path Traversal Prevention (VUL-002 Fixed):**
  - Path validation using canonical path resolution
  - Configurable allowed base directories (security.allowed_base_paths)
  - Defense-in-depth: validation at both indexer and MCP server layers
  - 24 comprehensive security tests covering traversal attempts
  - OWASP A01:2025 compliant

**Security Test Coverage:**
- 46 total security tests (all passing)
- Tests include: SQL injection patterns, path traversal attempts (../../), symlink attacks, absolute path validation
- Comprehensive vulnerability testing in `tests/security/`

**MCP Server Security:**
- Path validation before file operations
- TOCTOU (Time-of-check-time-of-use) vulnerability mitigation
- SecurityError exceptions for violations
- Detailed security logging

---

## Performance Benchmarks

**Search Performance:**
```
First search:       6-8 seconds (BGE model load)
Subsequent searches: 2-3 seconds
Memory usage:       ~2GB (BGE model on GPU)
```

**Indexing Performance:**
```
Per chunk:          1-2 seconds
Per document:       2-10 seconds (varies by length)
Chunks per doc:     2-5 (varies by length)
```

**Storage Efficiency:**
```
Example: 788 chunks = 3.2MB compressed (4KB per chunk avg)
```

---

## Troubleshooting

### Search returns no results

**Diagnosis:**
1. Check KB has chunks: `python -c "from rag import KnowledgeBaseIndexer; k=KnowledgeBaseIndexer('.vex-rag.yml'); print(k.get_stats())"`
2. Verify MCP server running: Check Claude Code session
3. Test direct search: `vex-search "test query"`
4. Check Ollama running: `curl http://localhost:11434/api/tags`

**Solutions:**
- If no chunks: Index documents first (`vex-index docs/ --batch`)
- If MCP offline: Restart Claude Code session
- If Ollama offline: `brew services restart ollama`
- If config missing: Create `.vex-rag.yml` from examples

### Slow searches (>5 seconds)

**Diagnosis:**
1. First search always slow (BGE model load ~6s) - **this is expected**
2. Subsequent searches should be ~2s
3. Check system resources: Activity Monitor

**Solutions:**
- First search: Expected, BGE loading (one-time cold start)
- Persistent slowness: Check Apple Silicon GPU usage
- Out of memory: Close other apps
- Disable reranking: Set `enable_reranking: false` in config (faster, less accurate)

### Indexing fails

**Diagnosis:**
1. Check file exists: `ls -la path/to/file`
2. Check file format supported: `.md`, `.pdf`, `.docx`, `.pptx`, `.txt`
3. Check Ollama running: `curl http://localhost:11434/api/tags`
4. Check models available: `ollama list | grep -E "(llama3.1|nomic-embed-text)"`

**Solutions:**
- File not found: Provide correct path
- Unsupported format: Convert to supported format
- Ollama offline: `brew services start ollama`
- Models missing: `ollama pull llama3.1:8b && ollama pull nomic-embed-text`

### Auto-indexing not working

**Diagnosis:**
1. Check git hook installed: `ls -la .git/hooks/post-commit`
2. Check hook executable: `test -x .git/hooks/post-commit && echo "OK"`
3. Check config: `.vex-rag.yml` → `indexing.auto_index_*`

**Solutions:**
- Hook missing: Create your own or check `~/tools/vex-rag/hooks/` (if included)
- Hook not executable: `chmod +x .git/hooks/post-commit`
- Config wrong: Update `auto_index_extensions` and `auto_index_paths`

---

## Advanced Usage

### Custom Chunking

Adjust chunk size in `.vex-rag.yml`:

```yaml
indexing:
  chunk_size: 512  # Larger chunks (default: 384)
  chunk_overlap: 0.20  # More overlap (default: 0.15)
```

**Trade-offs:**
- Larger chunks: More context per chunk, but fewer chunks (less granular)
- More overlap: Better context preservation, but more storage

### Custom Reranking

Use different reranker model:

```yaml
retrieval:
  enable_reranking: true
  reranker_model: BAAI/bge-reranker-base  # Smaller, faster
```

**Available models:**
- `BAAI/bge-reranker-large` - Best accuracy (default)
- `BAAI/bge-reranker-base` - Good accuracy, faster
- `BAAI/bge-reranker-v2-m3` - Multilingual support

### Disable Sanitization

For non-sensitive documents:

```yaml
indexing:
  enable_sanitization: false
```

Or per-file:

```bash
vex-index document.md --no-sanitize
```

---

## Development

### Running Tests

```bash
cd ~/tools/vex-rag

# Activate venv
source .venv/bin/activate

# Run tests
pytest tests/

# With coverage
pytest --cov=rag tests/
```

### Code Quality

```bash
# Format code
black rag/

# Lint code
ruff check rag/
```

### Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes
4. Run tests (`pytest tests/`)
5. Commit changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Open Pull Request

---

## Version History

See [PLUGIN-STATUS.md](PLUGIN-STATUS.md) for detailed version history and roadmap.

**Current:** v1.1.0 (January 3, 2026) - Documentation clarification and truth in advertising

**Recent Releases:**
- v1.1.0 - Clarified plugin capabilities, fixed misleading documentation
- v1.0.1 - CLI portability fixes, privacy improvements
- v1.0.0 - Initial public release

---

## Roadmap

See [PLUGIN-STATUS.md](PLUGIN-STATUS.md) for complete roadmap and planned features.

**Short-term (v1.2.0):**
- Implement `/rag-search` and `/rag-index` slash commands
- Create portable git hook package
- Improve installation UX

**Long-term (v2.0.0+):**
- Full Claude Code plugin integration
- Multi-modal support (images, audio, video)
- Advanced query features (query expansion, agentic retrieval)
- Enterprise features (multi-user, access control)

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Author

**Kelvin Lomboy**
Cybersecurity Consultant, Puerto Rico
🦖⚡ Professional excellence meets island living

**Email:** 0k.8csjy@8shield.net
**Website:** https://0k.cool
**GitHub:** https://github.com/0K-cool

---

## Acknowledgments

Built with:
- **LanceDB** - Local vector database
- **Sentence Transformers** - Embedding models
- **Ollama** - Local LLM inference
- **FastMCP** - MCP server framework
- **Anthropic Claude** - Model Context Protocol

Inspired by:
- **Anthropic's RAG recommendations** - Best practices for retrieval
- **Claude Code Plugin System** - Plugin architecture
- **100% local philosophy** - Privacy-first, zero cloud

---

## Support

**Documentation:** [GitHub](https://github.com/0K-cool/vex-rag)
**Issues:** [GitHub Issues](https://github.com/0K-cool/vex-rag/issues)
**Discussions:** [GitHub Discussions](https://github.com/0K-cool/vex-rag/discussions)

---

**Version:** 1.1.0
**Last Updated:** January 3, 2026
**100% Local Processing** - Zero Cloud APIs - Zero Cost
