# TODO 24 February

## Claude Code local integration — Phase 4-6

Decision: Option A + B combined (shell alias with separate HOME + bubblewrap
sandbox). See `docs/decisions/2026-02-24_claude-code-local-setup.md` for full
analysis.

### Phase 4: Dual-instance setup + sandboxing
- [x] Install bubblewrap and socat (`sudo apt install bubblewrap socat`)
- [x] Create `~/.claude-local/` with settings.json, CLAUDE.md, and skills
- [x] Create `claude-local/` repo folder with wrapper script, install.sh, README
- [x] Remove old `test/run.sh` (replaced by `claude-local/bin/claude-local`)
- [x] Remove `defaultMode: "plan"` from global settings and skill
- [x] Switch from HOME override to CLAUDE_CONFIG_DIR (fixes binary warnings, CLAUDE.md lookup)
- [x] Add IDE symlink workaround for VS Code integration (issue #4739)
- [x] Test: start local session, connects to llama-server, no OAuth conflict
- [x] Test: chat works, tool use works (Glob, Read, Write), thinking blocks visible
- [x] Test: VS Code IDE integration works (start from VS Code terminal, /ide detects VS Code)
- [x] Activate `/sandbox` and test:
  - [x] Can read/write within project workspace
  - [x] Bash write outside workspace: blocked
  - [x] Bash sudo: blocked
  - [x] Bash network (curl): blocked
  - [x] Bash commands require approval
  - [x] Claude Code ↔ llama-server API: works (not routed through bash)
  - **Finding:** Write/Edit tools are NOT sandboxed — can write anywhere. This is a
    Claude Code design limitation, not specific to the local setup. Documented in
    claude-local/README.md.
- [x] Document all findings in claude-local/README.md (onboarding, config, sandbox, safety warnings)

### Phase 5: Convenience and polish
- [x] Pre-flight check in wrapper (curl health check before starting claude)
- [x] Management API model switch works from claude-local session (~17s, session survives, context preserved)
  - **Note:** requires sandbox off (sandbox blocks bash network)
- [x] Document recommended workflow: when to use claude vs claude-local, model expectations, model switching
- Deferred to roadmap: auto-start llama-server from wrapper (opens start.sh in new terminal)

### Phase 6: Documentation
- [x] Create `docs/architecture.md` — C4-style architecture overview
- [x] Update README: Who is this for, What's next, Documentation links, Repository Structure
- [x] Update ROADMAP with Phase 4-6 completion status
- [x] Run doc-keeper consistency check (7 findings, all fixed)
- [x] Archive the integration plan

### Next: Hands-on testing
- [ ] Extensive hands-on testing of claude-local as implemented — use it for real
      tasks, try different models, explore edge cases. Findings and ideas feed into
      roadmap and future improvements.

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
