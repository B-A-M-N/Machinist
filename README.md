# Machinist

LLM autotooling pipeline with Ollama-only models, Bubblewrap sandboxing, and a provenance-aware tool registry.

## Flow
1. **Spec phase**: LLM produces a contract (name, signature, docstring, I/O types, failure modes, determinism).
2. **Implementation phase**: LLM emits only the tool code.
3. **Test phase**: LLM emits tests (unit, property-based via Hypothesis, abuse cases).
4. **Validation phase**: run lint/static, tests, coverage; enforce sandbox policy (bwrap, no network). Only then promote to registry.

## Key Features

### 🔍 Semantic Tool Search
The registry supports semantic search powered by `nomic-embed-text`. Find tools by describing what they do, even if you don't know the exact name.
- **Mode 6** in the CLI or `registry.search_tools("find files")`.

### 🔄 Complex Workflows
Compose tools into powerful workflows with logic:
- **Conditionals:** Skip steps based on output (`if_condition="$step.output"`).
- **Loops:** Iterate over lists (`foreach="$list"`).
- **Nesting:** Use entire workflows as atomic steps inside other workflows.

### 🛡️ Advanced Sandboxing
Execution is isolated using `bubblewrap` (bwrap) with strict resource limits enforced via `prlimit`:
- **Network:** Disabled (`--unshare-net`).
- **Memory:** 1GB limit (configurable).
- **CPU:** 60s time limit (configurable).
- **Filesystem:** Read-only system, writable scratchpad.

## Registry
Filesystem-backed (`registry/<tool_id>/metadata.json` + artifacts) storing spec, code path, tests path, test results, dependencies, security policy, capability profile, model provenance.

## LLM integration
`machinist/llm.py` defines an abstract `LLMClient`. `machinist/cli.py` contains `StubOllamaClient`; wire it to Ollama CLI or API (models available: `rnj-1:8b-cloud`, `phi4-mini`, `llama3.2`, `qwen3:4b`, `qwen2.5-coder:3b`).

## Interactive CLI
```bash
python -m machinist.cli
```
Prompts for goal and model (choices: `rnj-1:8b-cloud`, `phi4-mini`, `llama3.2`, `qwen3:4b`, `qwen2.5-coder:3b`), shows spec/code/tests, asks before validating in the sandbox, and asks before promoting to the registry.

### Non-Interactive / CI Mode
Automate tool creation and execution with flags:
```bash
# Generate a tool and auto-promote
python -m machinist.cli --mode 1 --goal "calculate square" --promote

# Run a workflow with inputs
python -m machinist.cli --mode 2 --goal "calculate square of 5" --inputs '{"number": 5}'

# Search for tools
python -m machinist.cli --mode 6 --goal "find files"
```

## Notes / TODO
- Add real Ollama client (streaming or batch).
- Consider mutation testing for high-value tools.
- Add persistence for test results and better coverage parsing.

## Licensing

This software is dual-licensed:

1.  **GNU Affero General Public License v3.0 (AGPL-3.0)**: This license applies to all non-commercial and public use of the software. You are free to use, modify, and distribute this software under the terms of AGPL-3.0.
2.  **Commercial License**: For commercial entities and businesses, commercial licensing terms are available. This option allows for use in proprietary projects without the copyleft obligations of AGPL-3.0.

For commercial licensing inquiries, please contact [Your Contact Information Here].