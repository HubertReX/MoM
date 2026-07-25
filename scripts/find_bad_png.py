import struct
import os


BAD_CHUNKS = {b'sRGB', b'gAMA', b'cHRM', b'iCCP'}
SKIP_DIRS = {
    'utils', 'screenshots', 'references', '.git', '.venv',
    '__pycache__', '.mypy_cache', '.egg-info', 'node_modules',
    'build', 'doc', 'Tasks',
}


def has_bad_chunk(fp: str) -> bool:
    with open(fp, 'rb') as f:
        if f.read(8) != b'\x89PNG\r\n\x1a\n':
            return False
        while True:
            buf = f.read(4)
            if len(buf) < 4:
                break
            length = struct.unpack('>I', buf)[0]
            ctype = f.read(4)
            if ctype in BAD_CHUNKS:
                return True
            if ctype == b'IEND':
                break
            f.seek(f.tell() + length + 4)
    return False


def main() -> None:
    for r, dirs, fs in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fs:
            if not fn.endswith('.png'):
                continue
            fp = os.path.join(r, fn)
            if has_bad_chunk(fp):
                path = fp[2:] if fp.startswith('./') else fp
                print(path)


if __name__ == '__main__':
    main()
