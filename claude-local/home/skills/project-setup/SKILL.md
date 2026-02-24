---
name: project-setup
description: "Interactive workflow for setting up a new project with the preferred structure, documentation, agents, and workflow. Guides through defining the project goal, creating foundational documents, setting up agents, and verifying consistency. Can also verify global Claude Code environment setup on a new PC."
---

# New Project Setup Workflow

You are guiding the user through setting up a new project with a clean, consistent structure. Follow the phases below in order. Do NOT skip phases unless the user explicitly asks to.

**Arguments:** The user may provide a project name or description. If not, ask for it in Phase 1.

**Mode:** If the user says "check global setup" or "verify environment", skip to Phase 0 only.

**Sandbox note:** This skill modifies files in `~/.claude-local/` (Phase 0) and
creates project files (Phases 2-5). When running with `/sandbox` active, writes
outside the project workspace are blocked — Phase 0 will not be able to fix global
settings. Run this skill **before** activating `/sandbox`. Once the project is set
up and the environment is verified, activate `/sandbox` for the rest of the session.

## Phase 0: Verify Global Environment (optional)

Only run this phase if the user asks to verify their global setup, or if this appears to be a new machine.

Check the following:

### 0.1 Global settings
Read `~/.claude-local/settings.json` and verify it contains:
```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "env": {
    "DISABLE_TELEMETRY": "1",
    "DISABLE_ERROR_REPORTING": "1",
    "BASH_DEFAULT_TIMEOUT_MS": "300000",
    "BASH_MAX_TIMEOUT_MS": "600000"
  },
  "alwaysThinkingEnabled": true,
  "plansDirectory": "./claude_plans"
}
```

If it differs, show the user what's wrong and ask if they want to fix it.

### 0.2 Global CLAUDE.md
Read `~/.claude-local/CLAUDE.md` and verify it contains the key sections:
- Local Instance Notice (warning about less capable model)
- Project structure template (with `AI_INSTRUCTIONS.md`, `concepts/`, `docs/lessons_learned.md`, `claude_plans/`, `archive/`, `.claude/agents/`)
- Plan mode rules (including rename-after-exit)
- Quality principles (SOLID, DRY, KISS)
- Always rules (read order, English-only, one source of truth, use agents)
- Communication style rules
- Git commit rules (no AI attribution)
- Compaction rules (including lessons_learned read order)

If sections are missing or outdated, tell the user what needs updating.

### 0.3 Orphaned plans
Check `~/.claude-local/plans/` — it should be empty. All plans should be project-local. If orphaned plans exist, ask the user if they can be deleted.

### 0.4 Global skills
Verify this skill exists at `~/.claude-local/skills/project-setup/SKILL.md`.

**Report findings and fix any issues before continuing to Phase 1.**

---

## Phase 1: Define the Project

### 1.0 Detect working context

Before asking any questions, determine WHERE the project will live:

1. Get the current directory path and extract the folder name
2. Check if the folder name is **generic** — any of: `home`, `Desktop`, `Documents`, `Downloads`, `repos`, `repositories`, `projects`, `workspace`, `workspaces`, `src`, `code`, `dev`, `tmp`, `temp`, `work`, or is the user's home directory (`~` / `$HOME`)
3. Check if the folder already contains **project files** — any of: `README.md`, `AI_INSTRUCTIONS.md`, `.claude/`, `package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `Makefile`, `.git/`
4. Determine the mode:
   - **Existing folder** — name is NOT generic AND/OR contains project files → work IN this directory
   - **Fresh start** — name IS generic AND no project files → will CREATE a subfolder
   - **Ambiguous** — ask the user via AskUserQuestion: "Set up here in `<folder>`?" or "Create a new subfolder?"

### 1.1 Project name

- **If existing folder:** suggest the current folder name as the project name using AskUserQuestion with two options: "Yes, use `<folder_name>`" and "No, different name". If the user chooses a different name, ask conversationally (not AskUserQuestion) for the name.
- **If fresh start:** ask conversationally for the project name (short, lowercase, hyphen-separated, e.g. `video-chat`, `api-monitor`).

### 1.2 Project details

**Ask the user the following questions** (use AskUserQuestion or conversation):

1. **One-line description** — what is this project?
2. **Goal** — what are we building and why?
3. **Use cases** — who uses it, for what? (list 3-5)
4. **Resources** — any repos to clone, APIs to integrate, models to use?
5. **Hardware/constraints** — relevant hardware, deployment target, VRAM limits?
6. **Development approach** — PoC/iterative/production? Sprint-based?

**Do NOT create any files yet.** Confirm understanding with the user before proceeding.

---

## Phase 2: Create Directory Structure

Behavior depends on the mode detected in Phase 1.0:

### Fresh start (creating a new subfolder)

Create the project skeleton inside a new directory:

```bash
mkdir -p <project_name>/{claude_plans,archive,concepts,docs,.claude/agents}
```

Then work inside this new directory for all subsequent phases.

If the user mentioned repos to clone, clone them now into the project root.

### Existing folder (working in current directory)

Only create subdirectories that don't already exist:

```bash
# Check and create each if missing:
mkdir -p claude_plans archive concepts docs .claude/agents
```

Note any existing files found (e.g. "Found existing README.md — will update rather than overwrite in Phase 3"). Do NOT overwrite existing files without asking.

---

## Phase 3: Create Foundational Documents

Create each document using the information gathered in Phase 1. Create them in this exact order — each one builds on the previous.

### 3.1 concepts/concept.md

The `concepts/` folder holds initial concepts and early design thinking. Create the main concept document:
- **Vision** — expanded goal statement
- **Core idea** — simple ASCII diagram showing the main flow
- **System context diagram** (C4 Level 1) — system and external actors (ASCII, keep it simple)
- **Container diagram** (C4 Level 2) — components inside the system (ASCII, keep it simple)
- **Input/output design** — phased table (MVP vs Later)
- **Key technical decisions** — model/framework/tool selection with rationale
- **Hardware/constraints** — what we have, what limits us
- **Available resources** — cloned repos, libraries, reference material
- **Use cases** — primary and secondary
- **Development approach** — iterative, SOLID/DRY/KISS

### 3.2 README.md

Create the project overview:
- Title and one-line description
- **Table of Contents** (links to all sections)
- Goal
- Architecture overview (simple ASCII diagram)
- Use cases (bullet list)
- Key technical choices (model, framework, etc.)
- Resources table (repos, dependencies)
- Hardware table (if relevant)
- Development approach (one line)
- Project Structure & Agents — **single line referencing AI_INSTRUCTIONS.md** (do NOT duplicate hierarchy here)
- Documentation links

### 3.3 AI_INSTRUCTIONS.md

Create the AI instruction file. **This is the single source of truth for hierarchy and agents.**
- **Project overview** — one paragraph
- **Principles** — SOLID/DRY/KISS, one source of truth, never delete (archive), modularity, English-only (see strong wording below), keep everything up to date, learn from mistakes, build on existing work, use agents (and update agent instructions after changes), local-first, Docker where possible (adapt to project)
  - **English rule (use this exact wording):** "ALL code, docs, comments, plans, and commit messages MUST be in English — always, no exceptions. The user often communicates in Dutch, but everything written to files must be English."
  - **Keep up to date:** "After any change, verify that docs, agent instructions, and config files still reflect reality. Stale docs are worse than no docs."
  - **Learn from mistakes:** "When an approach fails or wastes effort, document it in `docs/lessons_learned.md`. This file is persistent context for AI assistants to avoid repeating the same mistakes."
- **Workflow** — plan → ask approval → implement → test → iterate → clean up
- **Project hierarchy** — full file tree with descriptions (THE single source of truth — nowhere else)
- **Agents table** — placeholder, will be filled in Phase 5
- **Plan rules** — reference global rules, add project-specific if needed
- **Archive rules** — what goes to archive/
- **Git commits** — no AI attribution, only commit when asked
- **After compaction** — read order: this file → `docs/lessons_learned.md` → task tracker → active plans → concept → list contents of `claude_plans/`, `docs/`, `archive/` → continue

### 3.4 docs/lessons_learned.md

Create the lessons learned file with a header and format template:
- **Header** — purpose statement ("Ongoing log of what worked and what didn't... context for AI assistants")
- **Format template** — one example entry showing the Lesson / Example / Rule structure:

```markdown
# Lessons Learned

Ongoing log of what worked and what didn't during development. Primarily intended as context for AI assistants to avoid repeating mistakes, but useful for anyone picking up the project.

---

## [Title of the lesson]

**Lesson:** What was learned.

**Example:** What happened that taught this lesson.

**Rule:** The concrete rule to follow going forward.

---
```

This file should be referenced in the AI_INSTRUCTIONS.md principles ("Learn from mistakes") and in the compaction read order.

### 3.5 roadmap.md

Create sprint-based roadmap:
- Sprint 1 — MVP with concrete checkbox tasks
- Sprint 2+ — planned but less detailed
- Status table

### 3.6 Daily task tracker

Create `todo_<today's date>.md`:
- Group tasks by category
- Use checkboxes
- Mark completed items from this setup session

---

## Phase 4: Project-Level Settings

Create `.claude/settings.json` in the project:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "plansDirectory": "./claude_plans"
}
```

---

## Phase 5: Create Agents

### 5.1 Doc-keeper (offer to every project)

**Ask the user:** "Would you like a doc-keeper agent for documentation audits and consistency checks? (Recommended for any project with 3+ docs)"

If yes, create `.claude/agents/doc-keeper.md` with the following template, adapted to the project's actual files:

```markdown
---
name: doc-keeper
description: "Use this agent when documentation needs to be audited, maintained, or organized to ensure accuracy and consistency across the project. Specifically:\n\n- After making changes to the project — to verify documentation still reflects reality\n- When the user asks to \"clean up docs\", \"check if everything is up to date\", or \"organize documentation\"\n- After a session of iterative changes where multiple files were modified\n- When archiving or renaming files — to find and fix all broken references\n- Periodically as a maintenance sweep"
model: sonnet
---

You are an elite documentation architect and audit specialist. Your sole focus is **documentation accuracy and organization**. You do not write application code, configure infrastructure, or debug runtime issues. You read project state as source of truth and only change the documentation that describes it.

## Startup Procedure

Before doing anything else, read the following files in this exact order:
1. `AI_INSTRUCTIONS.md` — project rules, hierarchy, principles
2. `README.md` — user-facing overview
3. `roadmap.md` — current status and plans
[Add other key project files here]

## Source of Truth Hierarchy

When documents disagree, resolve using this priority order:
1. **`AI_INSTRUCTIONS.md`** — project rules, hierarchy, and principles
2. **Actual filesystem** — what files and directories really exist on disk
3. **`README.md`** — must conform to the above
4. **Everything else** — must conform to the above

## Core Capabilities

1. **Audit documentation state** — compare filesystem against documented hierarchies
2. **Detect stale content** — cross-reference data across documents for mismatches
3. **Suggest consolidation or archiving** — find redundant, superseded, or misplaced docs
4. **Update cross-references** — find and fix all references when files move
5. **Maintain hierarchy** — the project hierarchy lives in AI_INSTRUCTIONS.md only; README references it but does not duplicate it
6. **Verify completeness after changes** — check all docs are updated after project changes

## Report Format

### Up to Date
Brief summary of what's correct.

### Inconsistencies Found
- The specific inconsistency
- File and line/section references
- What the correct value should be

### Recommended Actions
Numbered list: what to do, which file(s), priority.

### Missing Documentation
Gaps where documentation should exist but doesn't.

## Inviolable Rules

1. Never delete files — always recommend archiving to `archive/` with date prefix
2. Everything in English
3. One source of truth — flag duplicates as problems
4. Read before suggesting changes
5. Present findings, don't auto-fix — ask before making edits
6. After file moves/renames, check ALL cross-references
7. When uncertain, ask
8. Respect project structure conventions from AI_INSTRUCTIONS.md
```

**Adapt this template** to the specific project: update the startup procedure with actual key files, adjust the source of truth hierarchy to include project-specific authoritative files, and add any project-specific capabilities or rules.

### 5.2 Additional agents (offer based on project needs)

Evaluate and **ask the user** about each:

| Agent | Offer when... |
|-------|---------------|
| `repo-researcher` | Project includes cloned or external reference repos. "Your project has cloned repos — want a read-only research agent for exploring them?" |
| `environment-setup` | Project needs infrastructure (Docker, GPU, Python envs, model downloads). "This project has infrastructure needs — want an environment setup agent?" |
| `builder` | Project has multiple components to wire together. "This project has multiple components — want a builder agent for Docker/compose/integration?" |

Only offer agents that make sense for the project. Don't offer all four if the project is a simple script.

### 5.3 For each agent to create

Write the agent definition with:
- **Frontmatter:** name, description (with 3+ usage examples), model: sonnet
- **Role statement:** what it does and explicitly what it does NOT do
- **Startup procedure:** which project files to read first
- **Source of truth hierarchy:** when documents disagree, what wins
- **Core capabilities:** numbered sections with descriptions
- **Report format:** structured output template
- **Inviolable rules:** hard constraints (never delete, English-only, read before changing, present findings before fixing, etc.)
- **Scope boundaries:** what's in/out of scope, with referrals to other agents

Create the agent by writing to `.claude/agents/<name>.md` or using the `/agents` command.

### 5.4 Update AI_INSTRUCTIONS.md

After all agents are created, update the agents table in `AI_INSTRUCTIONS.md` with every agent and its "when to use" description.

### 5.5 Project-specific skills (optional)

**Ask the user:** "Would you like to add project-specific skills? Skills are reusable workflows triggered by `/skill-name` — like this setup skill. They live in `.claude/skills/<name>/SKILL.md` inside the project. (You can always add them later.)"

**Skills vs agents:** Skills are step-by-step workflows you invoke on demand (like `/project-setup`). Agents are specialized personas with domain expertise that Claude can delegate to (like doc-keeper). Skills can be global (`~/.claude/skills/`) or project-specific (`.claude/skills/`). Agents are always project-specific (`.claude/agents/`).

If the user wants project-specific skills:
1. Ask for each skill: name and purpose (one sentence)
2. Create `.claude/skills/<name>/SKILL.md` with frontmatter (name, description) and a basic workflow skeleton
3. Repeat for additional skills, or continue when the user is done

If no: continue to Phase 6.

---

## Phase 6: Verify Consistency

Run the **doc-keeper** agent (if created) or manually verify:

- [ ] `AI_INSTRUCTIONS.md` hierarchy matches actual filesystem
- [ ] Agents table matches `.claude/agents/` contents
- [ ] `README.md` references `AI_INSTRUCTIONS.md` for hierarchy (not duplicated)
- [ ] All markdown links point to existing files
- [ ] No duplicate information across documents
- [ ] `roadmap.md` reflects the actual plan
- [ ] Daily task tracker reflects what was done today

Fix any inconsistencies found.

---

## Phase 7: Explain the Workflow

After everything is set up, explain to the user how to work with this structure:

### Daily workflow
1. **Start of session:** Claude reads `AI_INSTRUCTIONS.md` first, then task tracker, then active plans
2. **Planning work:** Use plan mode (`Shift+Tab`) → plan lands in `claude_plans/` → rename immediately after exit → implement → archive when done
3. **Using agents:** Agents handle specialized tasks (doc audits, repo research, environment, building). Use them instead of doing it manually.
4. **End of session:** Update task tracker. If tasks are done for the day, archive the tracker to `archive/`.

### Key principles to remember
- **AI_INSTRUCTIONS.md is the source of truth** — hierarchy, agents, rules all live there
- **Never duplicate** — if info exists in one place, reference it from others
- **Never delete** — archive to `archive/` with date prefix
- **English only** — all files, code, comments, commits
- **Plan mode first** — think before acting, rename the plan file after exit
- **Agents for their domain** — check the agents table before starting a task

### Available commands
- `/project-setup` — this skill (run again to verify or extend)
- `/agents` — manage agents
- `/skills` — see available skills
- `/compact` — compress context (will re-read AI_INSTRUCTIONS.md after)

---

## Phase Summary

| Phase | What happens |
|-------|-------------|
| 0. Environment | (Optional) Verify global Claude Code setup |
| 1. Define | Detect context (existing folder vs fresh start), gather project goals, use cases, constraints |
| 2. Structure | Create directories (new or fill gaps), clone repos |
| 3. Documents | Create concept, README, AI_INSTRUCTIONS, roadmap, task tracker |
| 4. Settings | Create project-level .claude/settings.json |
| 5. Agents & Skills | Create agents, optionally add project-specific skills |
| 6. Verify | Doc-keeper audit for consistency |
| 7. Explain | Teach the user the workflow |
