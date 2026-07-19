# Mode capability matrix

| Operation | Full | Minimal |
|---|---|---|
| Typed note capture | Transactional | Direct create and verify |
| Read/search | Indexed or live fallback | Direct filesystem search |
| Route/move one note | Transactional collision-safe move | Update, move, and verify without silently replacing a destination |
| Archive one note | Transactional | Update, move, and verify |
| Fleeting | Locked append | Preserve-and-append when available |
| Todo | SQLite plus Markdown transaction | Capture as clearly untracked inbox content |
| Import | Reviewed resumable pipeline | Preserve sources; requires full mode |
| Extract/dissolve | Multi-file transaction | Preserve notes; requires full mode |
| Index/context derivatives | Generated consistently | Leave stale until rebuilt |
| Backup/restore | Manifest verification | Ordinary external backup tools remain usable |

Both modes preserve the filesystem-first model. Full adds coordination and
recovery; minimal prioritizes legibility, portability, and low setup.

Markdown is canonical for documents. `todo.db` remains authoritative for
coordinated todo state, including while minimal leaves that state dormant.
