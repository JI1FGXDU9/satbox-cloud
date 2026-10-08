"""Shared private folder lookup; no framework or orbital imports."""
import hashlib
import os
from pathlib import Path

def private_folder(config_path=None, data_dir=None):
    config_path = Path(config_path or Path(__file__).parents[1] / 'web-qth.json').resolve()
    private_root = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    project_id = hashlib.sha256(str(config_path).encode()).hexdigest()[:12]
    return Path(data_dir or os.environ.get('SATBOX_DATA_DIR') or private_root / 'SatBoxCloud' / project_id).resolve()
