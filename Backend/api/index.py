import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
grandparent_dir = os.path.dirname(parent_dir)

for p in [
    current_dir,
    parent_dir,
    grandparent_dir,
    os.path.join(grandparent_dir, "Backend"),
    os.path.join(grandparent_dir, "backend"),
    os.path.join(parent_dir, "Backend"),
    os.path.join(parent_dir, "backend")
]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    from main import app  # noqa: E402
except ImportError:
    try:
        from Backend.main import app  # noqa: E402
    except ImportError:
        from backend.main import app  # noqa: E402
