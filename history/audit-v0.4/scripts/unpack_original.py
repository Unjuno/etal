"""Unpack the exact supplied ETAL archive into source/ without overwriting files."""
from pathlib import Path
import zipfile,hashlib

root=Path(__file__).resolve().parents[1]
archive=root/'inputs'/'ETAL_original_reproducibility.zip'
expected='0610cf1d6e0e3f224d3403ad15a725e8b1af044ccb6e6aba838937364dff86e5'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected,'Original archive digest mismatch'
dest=root/'source'
if dest.exists():
    raise SystemExit('source/ already exists. Use a new copy; this script never overwrites it.')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None,'Archive CRC error'
    for name in z.namelist():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
    z.extractall(dest)
print(dest/'etal_v02')
