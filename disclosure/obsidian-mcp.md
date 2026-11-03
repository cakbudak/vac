# Note to the maintainer of obsidian-mcp

Observed on `obsidian-mcp@2.0.1` (30–31 October 2026, two machines): every mutating tool call — 72
of 72 over three seeds — created a journal entry under `<vault>/.obsidian-mcp/transactions/`, and
`obsidian_delete_note` in trash mode created files under `.obsidian-mcp/trash/`.  The README
documents both locations; the tool descriptions say "transactionally" and "MCP trash" without
naming where.  A client that reads only `tools/list` cannot know that a note
edit creates files outside the note.  A sentence in each mutating tool's description ("journal under
.obsidian-mcp/transactions") would close the gap.  `obsidian_move_note` also rewrites every note that
links to the moved one, which the description declares in words; listing the rewritten paths in the
result would let a controller grade it.  Nothing here is a defect.

**Receipts** at https://github.com/cakbudak/vac (one JSON line per tool call), in
`real-mcp/results2/obsidian/seed-1/receipts_heldout.jsonl`:

- Journal entry: line 2 (`obsidian_create_note`), field `fs.created`.
- Trash file: line 14 (`obsidian_delete_note`, `mode: trash`).
- Linking note rewritten: line 12 (`obsidian_move_note`; `archive/outline.md` in `fs.modified`).
- The same on the second machine under `real-mcp/results2_second_machine/obsidian/`.
