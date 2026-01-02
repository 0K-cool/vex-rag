# Changelog

All notable changes to the Vex RAG Plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-02

### Added
- **Initial plugin extraction from PAI monolithic system**
- Configuration-driven architecture via `.vex-rag.yml`
- Project-portable MCP server with automatic context injection
- Slash commands: `/rag-search`, `/rag-index`
- RAG maintenance subagent for system operations
- Auto-indexing git hook for post-commit document indexing
- CLI tools: `vex-search`, `vex-index`
- Example configurations for PAI, VERSANT-IR, VERSANT-ATHENA
- Comprehensive README with installation and usage guide
- Python package structure with proper imports (rag.*)
- Multi-project support via configuration files
- Configurable logging and backup locations

### Features
- **Core RAG Pipeline:**
  - Contextual chunking (Llama 3.1 8B, boundary-aware, 384 tokens)
  - Vector search (nomic-embed-text, 768-dim)
  - BM25 keyword search (LanceDB FTS)
  - Reciprocal Rank Fusion (RRF)
  - BGE reranking (local, Apple Silicon GPU)
  - Native citations support (Anthropic format)

- **Infrastructure:**
  - 100% local processing (zero cloud APIs)
  - MCP server integration (automatic context injection)
  - Multi-project support (configurable via YAML)
  - PII sanitization (multi-layer, configurable)
  - Auto-indexing (git post-commit hooks)
  - Configurable backup/restore

- **Developer Experience:**
  - CLI tools (vex-search, vex-index)
  - Slash commands (/rag-search, /rag-index)
  - RAG maintenance subagent
  - Comprehensive documentation
  - Example configurations

### Performance
- First search: ~6 seconds (BGE model load)
- Subsequent searches: ~2 seconds
- Indexing: ~1-2 seconds per chunk
- Storage efficiency: ~4KB per chunk

### Security
- 100% local processing (zero data exfiltration)
- PII sanitization enabled by default
- Configurable per-project sanitization settings
- File permissions: 600/700 (owner only)

### Documentation
- Comprehensive README.md with installation guide
- Plugin design document (vex-rag-plugin-design.md)
- Example configurations for 3 project types
- Slash command documentation
- RAG maintenance agent guide
- Troubleshooting section

### Changed
- N/A (initial release)

### Deprecated
- N/A (initial release)

### Removed
- N/A (initial release)

### Fixed
- N/A (initial release)

### Security Notes
- PII sanitization enabled by default
- All processing done locally (zero cloud APIs)
- Configurable per-project sanitization settings

---

## [Unreleased]

### Planned for v1.0.1
- End-to-end test suite
- Bug fixes from user feedback
- Performance optimizations
- Enhanced error messages

### Planned for v1.1.0
- Multi-modal support (images, OCR, audio, video)
- Image indexing for screenshots and diagrams
- OCR for scanned documents
- Audio transcription support

### Planned for v1.2.0
- Advanced query features
- Query expansion/rewriting
- Agentic retrieval (iterative multi-step)
- Parent-child chunking
- Time-based filtering

### Planned for v1.3.0
- Testing & observability
- Comprehensive test suite
- Performance benchmarking
- Metrics dashboard
- Retry logic for failures

### Planned for v2.0.0
- Enterprise features
- Multi-user support
- Access control per project
- Audit logging
- Cost tracking

---

## Version Naming Convention

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR version** (v2.0.0) - Incompatible API changes
- **MINOR version** (v1.1.0) - New features, backwards compatible
- **PATCH version** (v1.0.1) - Bug fixes, backwards compatible

---

## Release Notes

### v1.0.0 - Plugin Extraction (January 2, 2026)

**Summary:** Initial extraction of Vex RAG system from Personal AI Infrastructure (PAI) monolithic codebase into a standalone, reusable Claude Code Plugin.

**Key Changes:**
- Extracted core RAG modules (indexing, retrieval) into `rag/` package
- Created configurable MCP server that reads from `.vex-rag.yml`
- Built portable CLI tools (vex-search, vex-index)
- Designed slash commands for Claude Code integration
- Implemented auto-indexing via git hook
- Created RAG maintenance subagent for operations

**Migration Path:**
- PAI (monolithic) → v1.0.0 (plugin) requires:
  1. Create `.vex-rag.yml` in project root
  2. Install plugin: `claude plugin install ~/tools/vex-rag`
  3. Copy existing LanceDB: `lance_vex_kb/` (no changes needed)
  4. Update MCP config to use new server location

**Breaking Changes:**
- None (initial release)

**Known Issues:**
- First search always slow (~6s) due to BGE model load (expected behavior)
- Auto-indexing hook requires manual installation per project
- Backup scripts are project-specific (not yet in plugin)

**Upgrade Notes:**
- None (initial release)

---

## Contributors

**v1.0.0:**
- Kelvin Lomboy (@kelvinlomboy) - Initial plugin extraction and design

---

## Links

- **Repository:** https://github.com/kelvinlomboy/vex-rag
- **Issues:** https://github.com/kelvinlomboy/vex-rag/issues
- **Documentation:** https://github.com/kelvinlomboy/vex-rag/blob/main/README.md
- **Changelog:** https://github.com/kelvinlomboy/vex-rag/blob/main/CHANGELOG.md
