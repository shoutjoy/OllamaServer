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


def hardware_capacity():
    """Return memory capacity used for conservative model-fit estimates."""
    result = {'cpu_threads': os.cpu_count() or 1, 'ram_total_gb': 0.0,
              'ram_available_gb': 0.0, 'vram_total_gb': 0.0,
              'vram_free_gb': 0.0, 'gpu_name': ''}
    if os.name == 'nt':
        try:
            memory = MemoryStatus()
            memory.length = ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                result['ram_total_gb'] = memory.total / 2**30
                result['ram_available_gb'] = memory.available / 2**30
        except (OSError, AttributeError):
            pass
    executable = shutil.which('nvidia-smi')
    if executable:
        try:
            output = subprocess.check_output([
                executable, '--query-gpu=name,memory.total,memory.free',
                '--format=csv,noheader,nounits'], text=True, encoding='utf-8',
                errors='replace', timeout=4, creationflags=NO_WINDOW)
            devices = []
            for line in output.splitlines():
                parts = [part.strip() for part in line.split(',')]
                if len(parts) == 3:
                    devices.append((parts[0], float(parts[1]) / 1024,
                                    float(parts[2]) / 1024))
            if devices:
                name, total, free = max(devices, key=lambda item: item[2])
                result.update(gpu_name=name, vram_total_gb=total, vram_free_gb=free)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return result


def model_size_gb(description):
    """Extract a catalog download size without confusing it with parameter counts."""
    matches = re.findall(r'(\d+(?:\.\d+)?)\s*(TB|GB|MB)\b', description or '', re.I)
    if not matches:
        return None
    value, unit = matches[-1]
    return float(value) * {'MB': 1 / 1024, 'GB': 1, 'TB': 1024}[unit.upper()]


def model_fit(size_gb, capacity, npu=False):
    """Classify expected placement; model size is expanded for runtime overhead."""
    if npu:
        return 'NPU · 지원 장치 확인'
    if not size_gb:
        return '미확인 · 태그 크기 필요'
    required = size_gb * 1.2
    vram = max(0.0, capacity.get('vram_free_gb', 0.0))
    ram = max(0.0, capacity.get('ram_available_gb', 0.0))
    if vram >= required:
        return 'FIT · VRAM 전체 적재'
    if vram >= min(1.0, required * .15) and vram + ram * .7 >= required:
        return 'PARTIAL · GPU+RAM 분할'
    if ram * .7 >= required:
        return 'OFFLOAD · CPU/RAM 실행'
    return '부족 · 더 많은 RAM/VRAM 필요'


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


def gpu_devices(rows, adapters):
    groups = {}
    names = {a['id'].lower(): a.get('name', '') for a in adapters}
    for row in rows:
        match = re.search(r'(luid_0x[0-9a-f]+_0x[0-9a-f]+)_phys_(\d+)', row.get('Name', ''), re.I)
        if match:
            groups.setdefault(match.group().lower(), []).append(row)
    result = []
    for key, engines in groups.items():
        luid = key.split('_phys_')[0]
        name = names.get(luid, '')
        # Only classify known integrated product names; never guess from GPU index.
        integrated = bool(re.search(r'Intel.*(?:UHD|Iris|HD Graphics)|Radeon.*(?:780M|680M|760M|890M)|^AMD Radeon(?:\(TM\))? Graphics$', name, re.I))
        discrete = bool(re.search(r'GeForce|Quadro|RTX|Radeon RX|Intel.*Arc.*A\d', name, re.I))
        neural = bool(re.search(r'\bNPU\b|\bIPU\b|Neural|AI Boost|Ryzen AI|Hexagon', name, re.I))
        kind = 'NPU' if neural else '내장' if integrated else '외장' if discrete else '유형 미확인'
        result.append({'id': key, 'name': name or key, 'kind': kind, 'usage': gpu_engine_percent(engines)})
    return result


class MemoryStatus(ctypes.Structure):
    _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in
        ('total', 'available', 'total_page', 'available_page', 'total_virtual', 'available_virtual', 'extended')]


class ResourceSampler:
    def __init__(self):
        self.previous = None
        self.nvidia = shutil.which('nvidia-smi')

    def sample(self):
        result = {'cpu': None, 'ram': None, 'gpu': None, 'npu': None,
                  'ram_detail': '', 'gpu_detail': '측정 불가', 'npu_detail': '측정 불가 · 장치/드라이버 확인'}
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
                result['ram_available'] = memory.available
                result['ram'] = used / memory.total * 100
                result['ram_detail'] = f'{used / 2**30:.1f} / {memory.total / 2**30:.1f} GB · 여유 {memory.available / 2**30:.1f} GB'
                if result['ram'] >= 85:
                    result['ram_detail'] += ' · RAM 부족: 컨텍스트/상주 모델 축소 권장'
        except (OSError, AttributeError):
            pass
        try:
            script = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$adapters = @(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\*\*' -ErrorAction SilentlyContinue | Where-Object { $_.AdapterLuid } | ForEach-Object {
 $bytes = [byte[]]$_.AdapterLuid
 if ($bytes.Length -eq 8) {
  $low = [BitConverter]::ToUInt32($bytes,0); $high = [BitConverter]::ToUInt32($bytes,4)
  @{ id=('luid_0x{0:x8}_0x{1:x8}' -f $high,$low); name=$_.DriverDesc }
 }
})
$engines = @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -ErrorAction Stop | Select-Object Name,UtilizationPercentage)
@{adapters=$adapters; engines=$engines} | ConvertTo-Json -Depth 4 -Compress
"""
            output = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                                    timeout=4, creationflags=NO_WINDOW, check=True)
            data = json.loads(output.stdout or '{}')
            devices = gpu_devices(data.get('engines', []), data.get('adapters', []))
            result['gpus'] = [device for device in devices if device['kind'] != 'NPU']
            npus = [device for device in devices if device['kind'] == 'NPU']
            result['npu'] = max((device['usage'] for device in npus if device['usage'] is not None), default=None)
            if npus:
                result['npu_detail'] = ' / '.join(device['name'] for device in npus)
            result['gpu'] = max((device['usage'] for device in result['gpus'] if device['usage'] is not None), default=None)
            result['gpu_detail'] = '장치별 Windows 엔진 사용률 · Ollama 전용 아님'
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
        self.canvas._theme_background = '#101827'
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
        devices = newest.get('gpus', [])
        columns = [('connected', '서버 연결', '#34d399')]
        columns += [(d['id'], d['kind'] + ' GPU', '#a78bfa') for d in devices] or [('gpu', 'GPU', '#a78bfa')]
        columns += [('npu', 'NPU', '#f472b6'), ('cpu', 'CPU', '#38bdf8'), ('ram', 'RAM', '#fb923c')]
        def metric(sample, key):
            device = next((d for d in sample.get('gpus', []) if d['id'] == key), None)
            return device['usage'] if device else sample.get(key)
        for index, (key, label, color) in enumerate(columns):
            left, right = index * width / len(columns) + 12, (index + 1) * width / len(columns) - 12
            value = metric(newest, key)
            text = ('연결됨' if value else '연결 안 됨') if key == 'connected' and value is not None else (
                f'{value:.1f}%' if value is not None else '측정 대기 / 불가')
            canvas.create_text(left, 15, text=label + '  ' + text, fill=color, anchor='w', font=('맑은 고딕', 10, 'bold'))
            detail = '127.0.0.1:11434' if key == 'connected' else newest.get(key + '_detail', '')
            device = next((d for d in devices if d['id'] == key), None)
            if device:
                detail = device['name']
            canvas.create_text(left, 35, width=right-left, text=detail, fill='#94a3b8', anchor='w', font=('맑은 고딕', 8))
            for level in (0, 50, 100):
                y = 112 - level * .55
                canvas.create_line(left, y, right, y, fill='#263449')
            points = []
            for stamp, item in self.samples:
                number = metric(item, key)
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
