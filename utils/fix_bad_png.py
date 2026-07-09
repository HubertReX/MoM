import os
import subprocess


SKIP_DIRS = {'utils', 'screenshots', 'references', '.git', '.venv',
             '__pycache__', '.mypy_cache', '.egg-info', 'node_modules',
             'build', 'doc', 'Tasks'}


def has_bad_chunks(path: str) -> bool:
    """Check if PNG has sRGB/gAMA/cHRM/iCCP chunks."""
    import struct
    with open(path, 'rb') as f:
        if f.read(8) != b'\x89PNG\r\n\x1a\n':
            return False
        while True:
            buf = f.read(4)
            if len(buf) < 4:
                break
            length = struct.unpack('>I', buf)[0]
            ctype = f.read(4)
            if ctype in (b'sRGB', b'gAMA', b'cHRM', b'iCCP'):
                return True
            if ctype == b'IEND':
                break
            f.seek(f.tell() + length + 4)
    return False


def main() -> None:
    root = r'project'
    tool = r'pngcrush.exe'

    for dirpath, subdirs, files in os.walk(root):
        # Skip excluded dirs in-place
        subdirs[:] = [d for d in subdirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith('.png'):
                continue
            fp = os.path.join(dirpath, fn)
            if not has_bad_chunks(fp):
                continue
            cmd = r'{} -q -ow -rem gAMA -rem sRGB -rem cHRM -rem iCCP -reduce "{}"'.format(tool, fp)
            subprocess.run(cmd, shell=True)


if __name__ == '__main__':
    main()


if __name__ == '__main__':
    main()
