# Machinist

LLM autotooling pipeline with Ollama-only models, Bubblewrap sandboxing, and a provenance-aware tool registry.

## Flow
1. **Spec phase**: LLM produces a contract (name, signature, docstring, I/O types, failure modes, determinism).
2. **Implementation phase**: LLM emits only the tool code.
3. **Test phase**: LLM emits tests (unit, property-based via Hypothesis, abuse cases).
4. **Validation phase**: run lint/static, tests, coverage; enforce sandbox policy (bwrap, no network). Only then promote to registry.

## Registry
Filesystem-backed (`registry/<tool_id>/metadata.json` + artifacts) storing spec, code path, tests path, test results, dependencies, security policy, capability profile, model provenance.

## Sandbox
`BwrapSandbox` isolates execution:
- `--unshare-all` + `--no-new-privs`
- read-only binds for system dirs
- writable scratch at `/scratch`
- tmpfs for `/tmp` and `/var/tmp`
- network disabled by default

Adjust policy in `machinist/sandbox.py`.

## LLM integration
`machinist/llm.py` defines an abstract `LLMClient`. `machinist/cli.py` contains `StubOllamaClient`; wire it to Ollama CLI or API (models available: `rnj-1:8b-cloud`, `phi4-mini`, `llama3.2`, `qwen3:4b`, `qwen2.5-coder:3b`).

## Interactive CLI
```
python -m machinist.cli
```
Prompts for goal and model (choices: `rnj-1:8b-cloud`, `phi4-mini`, `llama3.2`, `qwen3:4b`, `qwen2.5-coder:3b`), shows spec/code/tests, asks before validating in the sandbox, and asks before promoting to the registry.

## Notes / TODO
- Add real Ollama client (streaming or batch).
- Harden sandbox (cgroups, timeouts, size limits, capability filter).
- Consider mutation testing for high-value tools.
- Add persistence for test results and better coverage parsing.

## Licensing

This software is dual-licensed:

1.  **GNU Affero General Public License v3.0 (AGPL-3.0)**: This license applies to all non-commercial and public use of the software. You are free to use, modify, and distribute this software under the terms of AGPL-3.0.
2.  **Commercial License**: For commercial entities and businesses, commercial licensing terms are available. This option allows for use in proprietary projects without the copyleft obligations of AGPL-3.0.

For commercial licensing inquiries, please contact [Your Contact Information Here].

