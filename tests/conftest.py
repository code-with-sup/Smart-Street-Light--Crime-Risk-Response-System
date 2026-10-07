import os
import tempfile

# Keep tests away from the real incident database and evidence folder.
os.environ.setdefault("SENTINEL_DATA_DIR", tempfile.mkdtemp(prefix="sentinel-test-"))
