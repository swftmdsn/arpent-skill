# Execution capability matrix

| Operation | CLI | Filesystem |
|---|---|---|
| Typed note capture | Transactional | Direct create and verify |
| Read/search | Indexed or live fallback | Direct filesystem search |
| Route/move one note | Transactional no-replace | Update, move, and verify |
| Archive one note | Transactional | Update, move, and verify |
| Fleeting | Locked append | Preserve-and-append when available |
| Todo | SQLite plus Markdown transaction | Capture as clearly untracked inbox content |
| Import | Reviewed resumable pipeline | Preserve sources; use CLI for coordinated import |
| Extract/dissolve | Multi-file transaction | Use CLI for coordinated lineage updates |
| Index/context derivatives | Generated consistently | Leave stale until rebuilt |
| Backup/restore | Manifest verification | Ordinary external backup tools remain usable |

Both modes preserve the filesystem-first model. The CLI adds coordination and
recovery; filesystem mode prioritizes legibility, portability, and low setup.
