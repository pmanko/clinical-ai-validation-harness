"""Produce a reviewable Caddy candidate; never replace the live file here."""
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
original = source.read_text()
anchor = '\t# Everything else is the SPA (static assets + client-side routes).'
if original.count(anchor) != 1 or 'csim-superset:8088' in original:
    raise SystemExit('Unexpected or already updated Caddy configuration; inspect before applying.')
addition = '''\t# Synthetic CSiM Superset lab. Preserve the prefix for Superset's middleware.
\t@csim_root path /superset
\tredir @csim_root /superset/ 308
\thandle /superset/* {
\t\treverse_proxy csim-superset:8088 {
\t\t\ttransport http {
\t\t\t\t# Close idle connections before Gunicorn's two-second timeout.
\t\t\t\tkeepalive 1s
\t\t\t}
\t\t}
\t}

'''
target.write_text(original.replace(anchor, addition + anchor))
print('Prepared Caddy candidate; validate before replacing the live file.')
