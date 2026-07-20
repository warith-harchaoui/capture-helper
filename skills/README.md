# capture-helper as an agent skill

`skills/capture-helper/` packages `capture-helper` as a **Claude Skill** *and* an
**OpenCode skill** — both ecosystems read the same `SKILL.md` (YAML frontmatter
+ Markdown body + progressive-disclosure `references/`). Installing it lets an
agent discover capture-helper and run camera / microphone capture, live preview,
and scene-configurator operations on the user's behalf without the user opening
a terminal.

## Layout

```
skills/capture-helper/
├── SKILL.md                 # name + trigger-rich description + instructions
└── references/
    ├── cli-reference.md      # full subcommand + flag matrix, output contract
    ├── surfaces.md           # library, CLIs, API, MCP, and the /gui configurator
    └── triggers.md           # exhaustive, auditable trigger catalogue
```

Progressive disclosure: `SKILL.md` stays short and discoverable; the depth lives
in `references/*.md`, loaded only when a task needs it.

## Install for Claude Code / Claude Desktop

Skills live under `~/.claude/skills/` (user) or `.claude/skills/` (project). To
track this repo's copy rather than duplicate it, symlink it:

```bash
ln -sfn "$PWD/skills/capture-helper" ~/.claude/skills/capture-helper
# per-project instead:
mkdir -p /path/to/project/.claude/skills
ln -sfn "$PWD/skills/capture-helper" /path/to/project/.claude/skills/capture-helper
```

## Install for OpenCode

OpenCode reads skills from `~/.opencode/skills/` (or `~/.config/opencode/skills/`):

```bash
mkdir -p ~/.opencode/skills
ln -sfn "$PWD/skills/capture-helper" ~/.opencode/skills/capture-helper
```

## Keeping triggers enforced

The host model only sees `SKILL.md`'s `description` before deciding to load the
skill, so every real trigger must appear there. `references/triggers.md` is the
human-reviewable superset — keep the two in sync, and mirror the repo-root
`TRIGGERS.md` (the user-facing catalogue).

No secrets live in this skill: everything is local, ffmpeg-backed, and reads
only the cameras / microphones the OS already exposes. Camera and microphone
data never leave the machine.
