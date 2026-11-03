# Note to the maintainer of obsidian-mcp

Observed on `obsidian-mcp@2.0.1` (30–31 October 2026, two machines): every mutating tool creates journal entries
under `<vault>/.obsidian-mcp/transactions/`, locks under `.obsidian-mcp/locks/` and, for
`obsidian_delete_note` in trash mode, files under `.obsidian-mcp/trash/`.  The README documents all
three; the tool descriptions say "transactionally" and "MCP trash" without naming where.  A client
that reads only `tools/list` cannot know that a note edit creates files outside the note.  A
sentence in each mutating tool's description ("journal under .obsidian-mcp/transactions") would
close the gap.  `obsidian_move_note` also rewrites every note that links to the moved one, which
the description declares in words; listing the rewritten paths in the result would let a controller
grade it.  Nothing here is a defect.
