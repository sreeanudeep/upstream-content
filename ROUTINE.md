# Weekly pack routine

You are writing next week's idea pack for Upstream, a personal microlearning app. Do exactly this:

1. Read `STYLE.md` (the rules) and `index/titles.txt` (every idea already published: `topic | title | source`). Do not repeat an idea or a near-duplicate of one, even under a new title.
2. Work out the pack id: ISO year and week of today's date, as `YYYY-wWW` (for example `2026-w43`). If `packs/<id>.json` already exists, add `-b`, `-c` and so on.
3. Write `packs/<id>.json` with **200 ideas, 50 per topic**, interleaved by topic. The shape:
   ```json
   {"id": "2026-w43", "publishedAt": "2026-10-25", "ideas": [
     {"id": "2026-w43-001", "topic": "mind", "tags": ["decision-making"],
      "title": "...", "body": "...", "deeper": "...\n\n...\n\n...",
      "source": {"kind": "book", "title": "...", "author": "...", "url": "https://..."}}
   ]}
   ```
   `kind` is one of `book`, `paper`, `article`, `organization`, `wikipedia`, `talk`. `author` and `url` are optional (an organization has no author); `url` must be https.
   Idea ids are the pack id plus a 3-digit number, in order.
   Spread the sources: no single source more than 3 times in a pack. Mix famous ideas with less known but solid ones.
4. Run `python tools/build.py`. It validates every pack and rebuilds `manifest.json` and `index/titles.txt`. If it reports errors, fix the pack and run it again. **Never push while it fails.**
5. Commit with the message `pack: <id>` and push to `main`.

If you cannot finish (an error you cannot fix, or you are out of time), push nothing. A missing week is fine; a broken pack is not.
