"""Small Windows launcher used to package run.bat as run.exe."""
from pathlib import Path
import os
import sys


def main():
    base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    batch = base / 'run.bat'
    if not batch.is_file():
        raise FileNotFoundError(f'run.bat을 찾을 수 없습니다: {batch}')
    os.startfile(batch)


if __name__ == '__main__':
    main()
