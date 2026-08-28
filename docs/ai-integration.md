# AI integration

`.egp` projects are dense and hard to read by hand, which makes them a natural
fit for AI-assisted exploration. Two complementary options ship with this
project.

## MCP server

An optional [MCP](https://modelcontextprotocol.io) server exposes the parser as
tools to any MCP-compatible client (Claude Desktop, Claude Code, Cursor, …).

```bash
pip install "pyegp-parser[mcp]"
```

Then register the `pyegp-parser-mcp` command with your client:

```json
{
  "mcpServers": {
    "pyegp-parser": {
      "command": "pyegp-parser-mcp"
    }
  }
}
```

Tools provided:

| Tool | Purpose |
|---|---|
| `get_project_summary` | High-level overview — best first call |
| `get_sas_code` | Extract SAS code from tasks and code elements |
| `get_data_lineage` | Trace what data each element reads and produces |
| `get_queries` | Full Query Builder definitions (tables, joins, filters) |
| `parse_egp` | Full structured JSON for one project |
| `parse_egp_directory` | Bulk-parse a directory tree |

## Claude Skill

[`skills/pyegp-parser/SKILL.md`](https://github.com/lamiskin/pyegp-parser/blob/main/skills/pyegp-parser/SKILL.md)
is a portable
[Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
that teaches Claude when and how to parse `.egp` files with the CLI and how to
interpret the JSON — no running server required. Copy the
`skills/pyegp-parser/` folder into your `.claude/skills/` directory to use it.

## Which one?

Use the **MCP server** for interactive, on-demand parsing inside a client that
cannot run shell commands. Use the **Skill** for a portable, dependency-light
way to give any shell-capable agent the know-how — it pairs with the CLI and
`jq` and needs no server process.

Either way, give the model the [LLM context guide](LLM_CONTEXT.md) when it
needs to interpret parser output in depth.
