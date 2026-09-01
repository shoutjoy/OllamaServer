"""Embedded installer process transport: Windows pipes and POSIX controlling PTY."""
import codecs
import errno
import os
import signal
import subprocess
import sys

from console_runner import ConsoleRunner
from core import NO_WINDOW


class InstallTerminalRunner(ConsoleRunner):
    def __init__(self):
        super().__init__()
        self.master = None

    def run(self, args, output):
        if os.name == 'nt':
            return super().run(args, output)
        import pty
        import termios
        master, slave = pty.openpty()
        # Do not echo submitted passwords back into the app's output log.
        settings = termios.tcgetattr(slave)
        settings[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, settings)
        wrapper = ('import fcntl,os,sys,termios; '
                   'fcntl.ioctl(0,termios.TIOCSCTTY,0); '
                   'os.execvp(sys.argv[1],sys.argv[1:])')
        try:
            with self.lock:
                if self.cancel.is_set():
                    return -1
                self.process = subprocess.Popen([sys.executable, '-c', wrapper] + args,
                                                stdin=slave, stdout=slave, stderr=slave,
                                                start_new_session=True,
                                                env=dict(os.environ, TERM='dumb', NO_COLOR='1'))
                self.master = master
                process = self.process
            os.close(slave)
            slave = None
            decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
            while True:
                try:
                    data = os.read(master, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not data:
                    break
                output(decoder.decode(data))
            output(decoder.decode(b'', final=True))
            return process.wait()
        finally:
            with self.lock:
                self.master = None
                self.process = None
                os.close(master)
                if slave is not None:
                    os.close(slave)

    def send(self, text):
        if os.name == 'nt':
            return super().send(text)
        with self.lock:
            if self.master is None or self.process.poll() is not None:
                raise RuntimeError('입력을 받을 실행 중인 설치 작업이 없습니다.')
            os.write(self.master, (text + '\n').encode('utf-8'))

    def stop(self):
        self.cancel.set()
        with self.lock:
            process = self.process
            if not process or process.poll() is not None:
                return
            if os.name == 'nt':
                # Only the process tree created for this installation is targeted.
                result = subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=NO_WINDOW, timeout=10)
                if result.returncode and process.poll() is None:
                    raise RuntimeError('설치 프로세스를 중지하지 못했습니다. 관리자 권한이나 실행 중인 설치창을 확인하세요.')
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
