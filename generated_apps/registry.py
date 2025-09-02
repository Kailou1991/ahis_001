from pathlib import Path
BASE = Path(__file__).resolve().parent

def discover_apps():
    for child in BASE.iterdir():
        if child.is_dir() and (child / 'urls.py').exists() and (child / '__init__.py').exists():
            yield child.name