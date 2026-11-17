import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify():
    # This lock describes the organized release, not the original pre-trial byte layout.
    # Original experiment hashes are retained in research/reference-freeze.json.
    manifest=json.loads((ROOT/'research/release-source-lock.json').read_text())
    failures=[name for name,expected in manifest['sha256'].items() if not (ROOT/name).exists() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected]
    if failures:raise RuntimeError('Published release source changed: '+', '.join(failures))
    return manifest
