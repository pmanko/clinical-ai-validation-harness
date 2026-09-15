"""Prepare the public overview route without changing the live configuration."""
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
original = source.read_text()
anchor = '\t# Synthetic CSiM Superset lab. Preserve the prefix for Superset\'s middleware.'
if original.count(anchor) != 1 or '/superset/design' in original:
    raise SystemExit('Unexpected or already updated configuration; inspect before applying.')
addition = '''\t# Public guide: only the curated static overview, never the lab directory.
\tredir /superset/design /superset/design/ 308
\thandle_path /superset/design/* {
\t\troot * /srv/media/csim-design
\t\theader Cache-Control "no-cache"
\t\tfile_server
\t}

'''
target.write_text(original.replace(anchor, addition + anchor))
print('Prepared overview route candidate; validate before replacing the live file.')
