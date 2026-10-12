"""Local Windows resource sampling and a compact Tk live dashboard."""
import ctypes
import json
import math
import os
import re
import shutil
import subprocess
import time
from collections import deque
from tkinter import Canvas, ttk
from ctypes import wintypes

NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def cpu_percent(previous, current):
    if previous is None:
        return None
    idle = current[0] - previous[0]
    total = current[1] + current[2] - previous[1] - previous[2]
    return max(0.0, min(100.0, 100 * (total - idle) / total)) if total > 0 else None


def gpu_engine_percent(rows):
    # Sum processes sharing an engine, then show the busiest engine.
    engines = {}
    for row in rows:
        name = row.get('Name', '')
        match = re.search(r'luid_.*', name)
        value = float(row.get('UtilizationPercentage', 0))
        if match and math.isfinite(value):
            key = match.group()
            engines[key] = engines.get(key, 0) + value
    return min(100.0, max(engines.values())) if engines else None


class MemoryStatus(ctypes.Structure):
    _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in
        ('total', 'available', 'total_page', 'available_page', 'total_virtual', 'available_virtual', 'extended')]


class ResourceSampler:
    def __init__(self):
        self.previous = None
        self.nvidia = shutil.which('nvidia-smi')

    def sample(self):
        result = {'cpu': None, 'ram': None, 'gpu': None, 'ram_detail': '', 'gpu_detail': '측정 불가'}
        if os.name != 'nt':
            return result
        try:
            times = [wintypes.FILETIME() for _ in range(3)]
            if ctypes.windll.kernel32.GetSystemTimes(*(ctypes.byref(t) for t in times)):
                current = tuple((t.dwHighDateTime << 32) | t.dwLowDateTime for t in times)
                result['cpu'] = cpu_percent(self.previous, current)
                self.previous = current
            memory = MemoryStatus()
            memory.length = ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)) and memory.total:
                used = memory.total - memory.available
                result['ram'] = used / memory.total * 100
                result['ram_detail'] = f'{used / 2**30:.1f} / {memory.total / 2**30:.1f} GB'
        except (OSError, AttributeError):
            pass
        try:
            if self.nvidia:
                output = subprocess.run([self.nvidia, '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                                        capture_output=True, text=True, timeout=3, creationflags=NO_WINDOW, check=True)
                values = [float(line.strip()) for line in output.stdout.splitlines()]
                values = [v for v in values if math.isfinite(v) and 0 <= v <= 100]
                if values:
                    result['gpu'] = max(values)
                    result['gpu_detail'] = 'NVIDIA · 가장 바쁜 GPU'
                    return result
            script = ('Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine '
                      '-ErrorAction Stop | Select-Object Name,UtilizationPercentage | ConvertTo-Json -Compress')
            output = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                    capture_output=True, text=True, timeout=4, creationflags=NO_WINDOW, check=True)
            rows = json.loads(output.stdout or '[]')
            result['gpu'] = gpu_engine_percent(rows if isinstance(rows, list) else [rows])
            result['gpu_detail'] = 'Windows · 가장 바쁜 GPU 엔진' if result['gpu'] is not None else '측정 불가'
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            pass
        return result


class ResourcePanel(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text='실시간 상태 · 이 PC 전체 사용량 · 약 5초 간격 · 최근 5분', padding=6)
        self.samples = deque(maxlen=61)
        self.placement = ttk.Label(self, text='Ollama 모델 배치: 조회 대기', wraplength=950)
        self.placement.pack(fill='x', pady=(0, 4))
        self.canvas = Canvas(self, height=132, background='#101827', highlightthickness=0)
        self.canvas.pack(fill='x', expand=True)
        self.canvas.bind('<Configure>', lambda event: self.draw())

    def update_sample(self, sample):
        self.placement.configure(text=sample.get('placement', 'Ollama 모델 배치: 조회 대기'))
        self.samples.append((time.monotonic(), sample))
        self.draw()

    def draw(self):
        canvas = self.canvas
        canvas.delete('all')
        width = max(canvas.winfo_width(), 400)
        newest = self.samples[-1][1] if self.samples else {}
        now = self.samples[-1][0] if self.samples else time.monotonic()
        for index, (key, label, color) in enumerate([
                ('connected', '서버 연결', '#34d399'), ('gpu', 'GPU', '#a78bfa'),
                ('cpu', 'CPU', '#38bdf8'), ('ram', 'RAM', '#fb923c')]):
            left, right = index * width / 4 + 12, (index + 1) * width / 4 - 12
            value = newest.get(key)
            text = ('연결됨' if value else '연결 안 됨') if key == 'connected' and value is not None else (
                f'{value:.1f}%' if value is not None else '측정 대기 / 불가')
            canvas.create_text(left, 15, text=label + '  ' + text, fill=color, anchor='w', font=('맑은 고딕', 10, 'bold'))
            detail = '127.0.0.1:11434' if key == 'connected' else newest.get(key + '_detail', '')
            canvas.create_text(left, 35, text=detail, fill='#94a3b8', anchor='w', font=('맑은 고딕', 8))
            for level in (0, 50, 100):
                y = 112 - level * .55
                canvas.create_line(left, y, right, y, fill='#263449')
            points = []
            for stamp, item in self.samples:
                number = item.get(key)
                if number is None:
                    if len(points) >= 4:
                        canvas.create_line(*points, fill=color, width=2)
                    points = []
                    continue
                x = right - min(300, now - stamp) / 300 * (right - left)
                points.extend((x, 112 - number * .55))
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=2)
            elif points:
                x, y = points
                canvas.create_oval(x-2, y-2, x+2, y+2, fill=color, outline='')
            canvas.create_text(left, 124, text='5분 전', anchor='w', fill='#64748b', font=('맑은 고딕', 8))
            canvas.create_text(right, 124, text='현재', anchor='e', fill='#64748b', font=('맑은 고딕', 8))
