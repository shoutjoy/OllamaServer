"""Reclaim unreachable objects and optionally trim only this app's working set."""
import ctypes
import gc
import os
from ctypes import wintypes


def clean_memory(trim=False):
    collected = gc.collect()
    detail = f'미사용 객체 {collected}개 정리'
    if trim and os.name == 'nt':
        try:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentProcess.argtypes = []
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            kernel.K32EmptyWorkingSet.argtypes = [wintypes.HANDLE]
            kernel.K32EmptyWorkingSet.restype = wintypes.BOOL
            if not kernel.K32EmptyWorkingSet(kernel.GetCurrentProcess()):
                raise ctypes.WinError(ctypes.get_last_error())
            detail += ' · 앱 작업 집합 반환 완료 (사용 시 RAM이 다시 증가할 수 있음)'
        except (OSError, AttributeError) as exc:
            detail += f' · 작업 집합 반환 실패: {exc}'
    return detail
