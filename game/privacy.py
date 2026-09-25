"""Privacy policy for code paths that persist captured game pixels."""

from __future__ import annotations

# Every source file allowed to call an image writer for captured game pixels
# must be reviewed here. Asset download/cache code does not capture game pixels
# and is intentionally outside this list.
APPROVED_CAPTURE_WRITERS = frozenset({
    "scraping/itemsScraper.py",
    "scraping/weaponsScraper.py",
    "scraping/echoesScraper.py",
    "tools/capture_diagnostics.py",
})
