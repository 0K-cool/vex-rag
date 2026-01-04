# Vex RAG Plugin - Status & Roadmap

**Last Updated:** January 3, 2026
**Current Version:** 1.1.0
**Maintainer:** Kelvin Lomboy (@0K-cool)

---

## 🎯 What is Vex RAG?

Vex RAG is a **100% local RAG system** distributed as:
1. **Python library** (`rag` module)
2. **MCP server** (automatic context injection)
3. **CLI tools** (`vex-search`, `vex-index`)

**Architecture Model:** Library + MCP Server + CLI Tools
**Not:** Full-featured Claude Code plugin (yet)

---

## ✅ Current Features (v1.1.0)

### Core Functionality (Production-Ready)

**Python Library:**
- ✅ Contextual chunking (Llama 3.1 8B via Ollama)
- ✅ Vector search (nomic-embed-text, 768-dim)
- ✅ BM25 keyword search (LanceDB FTS)
- ✅ Reciprocal Rank Fusion (RRF)
- ✅ BGE reranking (Apple Silicon GPU optimized)
- ✅ Multi-project support via configuration
- ✅ PII sanitization (multi-layer, configurable)
- ✅ Native citations (Anthropic citations API)
- ✅ Security hardening (SQL injection, path traversal protection)

**MCP Server:**
- ✅ `vex-knowledge-base` MCP server
- ✅ Resource: `vex://search/{query}` (automatic context injection)
- ✅ Tool: `index_document(file_path, project, sanitize)`
- ✅ Tool: `get_kb_stats()`
- ✅ Configuration-driven (`.vex-rag.yml`)
- ✅ Per-project isolation

**CLI Tools:**
- ✅ `vex-search` - Search knowledge base from terminal
- ✅ `vex-index` - Index documents from terminal
- ✅ Installed to system PATH via pip
- ✅ Full help documentation (`--help`)

**Testing & Quality:**
- ✅ 46 security tests (SQL injection + path traversal)
- ✅ 100% test pass rate
- ✅ Production-ready code quality
- ✅ Comprehensive documentation

**Installation:**
- ✅ Standard Python package (`pip install -e .`)
- ✅ Virtual environment isolation
- ✅ Clear installation documentation
- ✅ Example configurations for multiple use cases

---

## ⚠️ Not Yet Implemented

### Planned Features (Future Versions)

**Slash Commands:**
- ❌ `/rag-search` - Search via Claude Code slash command
- ❌ `/rag-index` - Index via Claude Code slash command
- Status: Not implemented (command files don't exist)
- Priority: Medium (nice-to-have, CLI tools provide same functionality)

**Subagents:**
- ❌ `rag-maintenance` - Portable subagent for RAG operations
- Status: Implemented as PAI-specific skill, not portable with plugin
- Priority: Low (current skill implementation works well)

**Hooks:**
- ❌ Portable `post-commit` hook for auto-indexing
- Status: Implemented per-project, not packaged with plugin
- Priority: Medium (manual setup works but not portable)

**One-Click Installation:**
- ❌ `claude plugin install ~/tools/vex-rag`
- Status: Claude Code plugin system doesn't support this yet
- Priority: Depends on Anthropic's plugin architecture evolution

---

## 🏗️ Architecture Decision

### Why "Library + MCP Server" vs "Full Plugin"?

**Current Choice: Library + MCP Server Model**

**Reasoning:**
1. **Claude Code plugin system is immature** - Slash commands, hooks, and subagents lack clear implementation patterns
2. **MCP server is the core value** - Automatic context injection is what matters most
3. **CLI tools provide same functionality** - `vex-search` and `vex-index` work great from terminal
4. **Easier to maintain** - Less magic, more explicit configuration
5. **Portable across environments** - Works in any Python project, not just Claude Code

**Trade-offs:**
- ✅ **Pro:** Core functionality is rock-solid and tested
- ✅ **Pro:** Installation is standard Python workflow
- ✅ **Pro:** No dependence on evolving plugin architecture
- ⚠️ **Con:** More manual setup (MCP config in `.mcp.json`)
- ⚠️ **Con:** No slash commands (use CLI tools instead)

**Future Path:**
When Claude Code's plugin system matures and patterns emerge, we can revisit full plugin integration. For now, the current model provides **100% of the value** with **less complexity**.

---

## 📊 Feature Comparison

| Feature | Status | Alternative |
|---------|--------|-------------|
| **Automatic context injection** | ✅ MCP resource | N/A (core feature) |
| **Search knowledge base** | ✅ CLI `vex-search` | Slash command (planned) |
| **Index documents** | ✅ CLI `vex-index` | Slash command (planned) |
| **Get KB stats** | ✅ MCP tool | Slash command (planned) |
| **Python library** | ✅ `import rag` | N/A (core feature) |
| **Auto-indexing** | ⚠️ Manual setup | Portable hook (planned) |
| **Maintenance tasks** | ⚠️ Project skill | Portable subagent (planned) |

**Legend:**
- ✅ = Fully implemented and tested
- ⚠️ = Requires manual per-project setup
- ❌ = Not implemented

---

## 🚀 Roadmap

### v1.1.0 (Current - January 2026)
- ✅ Clarify plugin capabilities
- ✅ Remove misleading `claude plugin install` reference
- ✅ Document actual installation workflow
- ✅ Security hardening complete (VUL-001, VUL-002)
- ✅ 46 security tests passing

### v1.2.0 (Planned - Q1 2026)
- [ ] Implement `/rag-search` slash command
- [ ] Implement `/rag-index` slash command
- [ ] Create portable git hook package
- [ ] Improve installation UX

### v2.0.0 (Future - TBD)
- [ ] Full Claude Code plugin integration
- [ ] Portable subagent implementation
- [ ] One-command installation
- [ ] Enhanced automation features

**Note:** Roadmap is tentative and depends on:
1. Anthropic's Claude Code plugin system evolution
2. User feedback and feature requests
3. Available development time

---

## 💪 What Works Great TODAY

Don't let the roadmap fool you - **vex-rag is production-ready NOW**:

**For Individual Users:**
- ✅ 100% local RAG with zero cloud costs
- ✅ Automatic context injection in conversations
- ✅ Fast, accurate hybrid search + reranking
- ✅ Security-hardened for production use
- ✅ Well-documented and tested

**For Developers:**
- ✅ Python library for custom integrations
- ✅ CLI tools for automation/scripting
- ✅ MCP server for Claude Code integration
- ✅ Configuration-driven, portable across projects

**For Teams:**
- ✅ Per-project knowledge bases
- ✅ Shared configuration templates
- ✅ Consistent indexing and retrieval
- ✅ Security controls (path validation, sanitization)

---

## 🎯 Installation Reality Check

**What the README used to say:**
> "Install with a single command: `claude plugin install ~/tools/vex-rag`"

**What actually works (v1.1.0):**
```bash
# 1. Clone repo
git clone https://github.com/0K-cool/vex-rag.git ~/tools/vex-rag

# 2. Install Python package
cd ~/tools/vex-rag
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. Pull Ollama models
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# 4. Configure your project
cd ~/your-project
cp ~/tools/vex-rag/examples/config.pai.yml .vex-rag.yml

# 5. Setup MCP server (edit .mcp.json manually)
# 6. Start using!
```

**Time to install:** 10-15 minutes (mostly Ollama model downloads)
**Complexity:** Standard Python package installation
**One-time setup:** Yes, then works across all projects

---

## 🔍 For Plugin Developers

If you're considering using vex-rag as a reference for your own Claude Code plugin:

**Use this as a model for:**
- ✅ MCP server implementation (FastMCP, clean architecture)
- ✅ Configuration management (YAML-based, per-project)
- ✅ Security hardening (path traversal, SQL injection prevention)
- ✅ Python packaging (`pyproject.toml`, entry points)
- ✅ CLI tool design (argparse, clear help)
- ✅ Testing approach (security tests, integration tests)

**Don't expect:**
- ❌ Slash command implementation (not done yet)
- ❌ Portable hooks (project-specific)
- ❌ Subagent packaging (project-specific)
- ❌ One-command installation (manual setup required)

---

## 📝 Version History

### v1.1.0 (January 3, 2026)
- Clarified plugin capabilities in `plugin.json`
- Fixed misleading installation documentation
- Added this PLUGIN-STATUS.md document
- Updated README with accurate installation steps
- No functional changes (core system unchanged)

### v1.0.1 (January 2, 2026)
- CLI portability fixes (entry points vs shebangs)
- Ollama API compatibility (name/model key handling)
- Privacy improvements (generic names in public examples)

### v1.0.0 (January 2, 2026)
- Initial public release
- Core RAG functionality complete
- MCP server integration
- CLI tools
- Security hardening (VUL-001, VUL-002 fixed)

---

## 🤝 Contributing

**Current Status:** Personal project, limited bandwidth for contributions

**If you want to help:**
1. Use vex-rag and provide feedback (GitHub issues)
2. Share your use cases and configurations
3. Report bugs with detailed reproduction steps
4. Suggest features with clear use cases

**Major contributions welcome for:**
- Slash command implementation
- Portable hook packaging
- Installation UX improvements
- Additional security tests

---

## 📞 Support & Community

**Questions or Issues?**
- GitHub Issues: https://github.com/0K-cool/vex-rag/issues
- Documentation: https://github.com/0K-cool/vex-rag/blob/main/README.md

**Philosophy:**
> "Truth in advertising. Build what works, document honestly, improve iteratively." - Vex 🦖⚡

---

**TL;DR:** Vex RAG is a **production-ready library + MCP server + CLI tools** for 100% local RAG. Not a full-featured Claude Code plugin (yet), but works great as-is. Install via pip, configure per-project, enjoy automatic context injection in Claude Code conversations.
