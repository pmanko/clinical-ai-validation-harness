"""Write a candidate route for the independent Superset development snapshot."""
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
original = source.read_text()
anchor = '\t# Everything else is the SPA (static assets + client-side routes).'
if original.count(anchor) != 1 or 'csim-superset-preview:8088' in original:
    raise SystemExit('Unexpected or already configured preview route; inspect before applying.')
addition = '''\t# Independent upstream Superset snapshot.
\tredir /superset-preview /superset-preview/ 308
\thandle /superset-preview/* {
\t\treverse_proxy csim-superset-preview:8088 {
\t\t\ttransport http {
\t\t\t\tkeepalive 1s
\t\t\t}
\t\t}
\t}

'''
target.write_text(original.replace(anchor, addition + anchor))
print('Prepared preview route candidate.')
