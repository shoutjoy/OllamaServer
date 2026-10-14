"""Non-interactive pipe transport for the embedded console (no shell)."""
import codecs
import os
import re
import subprocess
import threading

from core import NO_WINDOW

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07)')


class ConsoleRunner:
    def __init__(self, base_url='http://127.0.0.1:11434'):
        self.base_url = base_url
        self.process = None
        self.lock = threading.Lock()
        self.cancel = threading.Event()

    def run(self, args, output):
        env = dict(os.environ, OLLAMA_HOST=self.base_url, NO_COLOR='1', TERM='dumb')
        with self.lock:
            if self.cancel.is_set():
                return -1
            self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, env=env, bufsize=0,
                                            creationflags=NO_WINDOW)
            process = self.process
        decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        try:
            while True:
                data = os.read(process.stdout.fileno(), 4096)
                if not data:
                    break
                output(decoder.decode(data))
            output(decoder.decode(b'', final=True))
            return process.wait()
        finally:
            for pipe in (process.stdin, process.stdout):
                pipe.close()
            with self.lock:
                self.process = None

    def send(self, text):
        with self.lock:
            if not self.process or self.process.poll() is not None:
                raise RuntimeError('입력을 받을 실행 중인 명령이 없습니다.')
            self.process.stdin.write((text + '\n').encode('utf-8'))
            self.process.stdin.flush()

    def stop(self):
        self.cancel.set()
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
