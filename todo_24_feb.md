# TODO 24 February

## Claude Code local integration — Phase 4-6

Decision: Option A + B combined (shell alias with separate HOME + bubblewrap
sandbox). See `docs/decisions/2026-02-24_claude-code-local-setup.md` for full
analysis.

### Phase 4: Dual-instance setup + sandboxing
- [ ] Install bubblewrap and socat (`sudo apt install bubblewrap socat`)
- [ ] Create `~/.claude-local/` with minimal settings.json for the local instance
- [ ] Create `claude-local` wrapper script (replaces `test/run.sh`)
- [ ] Test: start local session, verify it connects to llama-server, check no
      OAuth credential conflict
- [ ] Activate `/sandbox` in local session, verify:
  - [ ] Can read/write within project workspace
  - [ ] Cannot write outside workspace
  - [ ] sudo is blocked (kernel-level via PR_SET_NO_NEW_PRIVS)
  - [ ] localhost:8080 reachable (llama-server API)
  - [ ] VS Code IDE integration works (diagnostics via MCP)
  - [ ] Bash commands require approval (not auto-accepted)

### Phase 5: Convenience and polish
- [ ] Final wrapper script with model selection support
- [ ] Verify management API model switching works from local Claude Code session
- [ ] Document recommended workflow (when to use which instance)

### Phase 6: Documentation
- [ ] Create `docs/architecture.md` — C4-style overview of how all components
      connect (wrapper, Docker, llama-server, dashboard, management API, Claude
      Code normal vs local, sandboxing). Include diagrams and design rationale.
- [ ] Plan README restructure for user-friendly flow: requirements → install →
      run a model → use with Claude Code. Quick Start stays concise, detailed
      guides in `docs/`. Structure defined in the plan — actual rewrite can happen
      in a later sprint.
- [ ] Update ROADMAP with Phase 4-6 completion status
- [ ] Update README "What's next" section
- [ ] Run doc-keeper consistency check
- [ ] Archive the integration plan and this todo when complete

## Ongoing

### llama.cpp upstream merge
- Waiting for `ggml_set_inplace` -> `ggml_set` fix to merge into master
- Running patched `ed4837891` locally
- Check: https://github.com/ggml-org/llama.cpp/issues/19816
- Note: patch is no longer load-bearing — migrated to FIT auto (no `-ot`)

## Not this session (but keep in mind)

### API integration with external tools
- Connect Continue.dev, aider, OpenClaw, etc. to the local server
- Depends on local Claude Code integration being stable first
- Defer to a future session
