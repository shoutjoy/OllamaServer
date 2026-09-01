"""Cancellable installer transfer; never expose an incomplete executable."""
from core import INSTALL_URL, open_url


class DownloadCancelled(Exception):
    pass


def download_installer(installer, cancel, progress):
    partial = installer.with_suffix('.download')
    def check():
        if cancel.is_set():
            raise DownloadCancelled()
    try:
        check()
        installer.parent.mkdir(parents=True, exist_ok=True)
        with open_url(INSTALL_URL, timeout=10) as response, partial.open('wb') as output:
            total = int(response.headers.get('Content-Length', 0))
            count = 0
            while True:
                check()
                chunk = response.read1(64 * 1024)
                check()
                if not chunk:
                    break
                output.write(chunk)
                count += len(chunk)
                progress(count, total)
            if total and count != total:
                raise RuntimeError('설치 파일 다운로드가 불완전합니다.')
        check()
        partial.replace(installer)
    except Exception:
        check()
        raise
    finally:
        partial.unlink(missing_ok=True)
