# Claude Code Extensibility — Quick Reference

Overview of the different ways to extend and customize Claude Code behavior.

## Agents

**What:** Specialized AI assistants with custom instructions and tool access. Each runs in its own context.

**Where:** `.claude/agents/<name>.md` (project) or `~/.claude/agents/<name>.md` (personal)

**When to use:**
- Focused tasks that need domain knowledge (GPU optimization, benchmarking, documentation audits)
- Tasks where you want to restrict which tools are available
- Repetitive work with consistent requirements

**How to trigger:** Claude auto-detects from the agent's `description` field, or you explicitly ask "use the gpu-optimizer agent"

**Limitations:** Agents can't call other agents. Orchestration happens from the main conversation.

## Skills

**What:** Reusable instruction sets that get injected into Claude's context when invoked. Essentially a structured prompt with optional dynamic values.

**Where:** `.claude/skills/<name>/SKILL.md` (project) or `~/.claude/skills/<name>/SKILL.md` (personal)

**When to use:**
- Multi-step workflows you want to run the same way every time
- Custom slash commands (`/add-model`, `/deploy`, `/review`)
- Injecting live data into prompts (via `` !`command` `` syntax)

**How to trigger:** `/skill-name` or `/skill-name arguments`. Can also auto-trigger based on description.

**Key difference from agents:** A skill is instructions that Claude follows in the current conversation. An agent is a separate context with its own tools and focus. Skills can tell Claude to use specific agents at specific steps.

## Hooks

**What:** Shell commands that run automatically at specific lifecycle events (before/after tool use, on session start, etc.).

**Where:** `.claude/settings.json` under the `hooks` key

**When to use:**
- Auto-formatting code after edits (run Prettier, Black, etc.)
- Blocking edits to protected files
- Running tests after file changes
- Sending notifications when Claude needs input

**How to trigger:** Automatic — fires at the configured lifecycle event.

**Key events:** `PreToolUse` (can block), `PostToolUse`, `SessionStart`, `UserPromptSubmit`, `PreCompact`

**Limitations:** Shell commands only, no LLM access. Reactive, not proactive.

## MCP Tools

**What:** External integrations via the Model Context Protocol (GitHub, databases, Slack, etc.).

**Where:** `.claude/settings.json` under `mcpServers`

**When to use:** When Claude needs to interact with external services that aren't accessible via standard tools.

**How to trigger:** Claude uses them automatically when relevant, like any other tool.

## Agent Teams (experimental)

**What:** Multiple independent Claude Code instances working in parallel, coordinated by a team lead. Unlike subagents, teammates have their own full context windows and can communicate through a shared task list and messaging system.

**Where:** Enable in `.claude/settings.json`:
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

**When to use:**
- Parallel independent tasks (e.g., one reviews code while another writes tests)
- Competing approaches to the same problem
- Large cross-layer changes where each teammate handles a different area

**How to trigger:** Claude spawns teammates automatically when it determines parallel work would help.

**Limitations:** Experimental, disabled by default. Uses significantly more tokens (each teammate gets its own context). Works with Claude subscription (Pro/Max), no separate API key needed.

## CLAUDE.md / AI_INSTRUCTIONS.md

**What:** Project-level instructions that persist across sessions. Guides Claude's behavior through natural language.

**Where:** `CLAUDE.md` in project root or `~/.claude/CLAUDE.md` (personal)

**When to use:** Always — this is where you put project conventions, architecture decisions, and workflow guidance.

## When to use what

| I want to... | Use |
|---|---|
| Give a focused task to a specialist | Agent |
| Run a repeatable multi-step workflow | Skill |
| Auto-run something after every edit | Hook |
| Connect to an external service | MCP Tool |
| Set project-wide conventions | CLAUDE.md |
| Guide which agent to use when | Skill (orchestrator) or CLAUDE.md |
| Run multiple independent tasks in parallel | Agent Teams (experimental) |
