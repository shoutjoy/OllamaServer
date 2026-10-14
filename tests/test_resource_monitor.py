import unittest
import json
import subprocess
from unittest.mock import patch
from resource_monitor import cpu_percent, gpu_engine_percent, ResourceSampler


class ResourceTests(unittest.TestCase):
    def test_cpu_uses_delta_and_kernel_includes_idle(self):
        self.assertIsNone(cpu_percent(None, (20, 60, 40)))
        self.assertEqual(cpu_percent((0, 0, 0), (20, 60, 40)), 80)
        self.assertIsNone(cpu_percent((20, 60, 40), (20, 60, 40)))

    def test_gpu_sums_processes_per_engine_not_unrelated_engines(self):
        rows = [
            {'Name': 'pid_1_luid_0x0_0x1_phys_0_eng_0_engtype_Compute', 'UtilizationPercentage': 40},
            {'Name': 'pid_2_luid_0x0_0x1_phys_0_eng_0_engtype_Compute', 'UtilizationPercentage': 30},
            {'Name': 'pid_1_luid_0x0_0x1_phys_0_eng_1_engtype_Copy', 'UtilizationPercentage': 50}]
        self.assertEqual(gpu_engine_percent(rows), 70)
        self.assertIsNone(gpu_engine_percent([]))
        self.assertIsNone(gpu_engine_percent([{'Name': 'unrecognized', 'UtilizationPercentage': 80}]))

    def test_gpu_failure_is_unknown_not_zero(self):
        sampler = ResourceSampler()
        with patch('resource_monitor.subprocess.run', side_effect=OSError('unavailable')):
            sample = sampler.sample()
            self.assertIsNone(sample['gpu'])
            self.assertIsNone(sample['npu'])

    def test_sampler_separates_npu_from_gpu_and_sums_shared_engine(self):
        rows = [
            {'Name': 'pid_1_luid_0x00000000_0x00000001_phys_0_eng_0_engtype_Compute', 'UtilizationPercentage': 20},
            {'Name': 'pid_1_luid_0x00000000_0x00000002_phys_0_eng_0_engtype_Compute', 'UtilizationPercentage': 35},
            {'Name': 'pid_2_luid_0x00000000_0x00000002_phys_0_eng_0_engtype_Compute', 'UtilizationPercentage': 40}]
        data = {'engines': rows, 'adapters': [
            {'id': 'luid_0x00000000_0x00000001', 'name': 'NVIDIA GeForce RTX 4060'},
            {'id': 'luid_0x00000000_0x00000002', 'name': 'AMD IPU Device'}]}
        output = subprocess.CompletedProcess([], 0, json.dumps(data))
        with patch('resource_monitor.os.name', 'nt'), patch('resource_monitor.subprocess.run', return_value=output):
            sample = ResourceSampler().sample()
        self.assertEqual(sample['gpu'], 20)
        self.assertEqual(sample['npu'], 75)
        self.assertEqual(len(sample['gpus']), 1)
        self.assertIn('AMD IPU Device', sample['npu_detail'])


class DeviceTests(unittest.TestCase):
    def test_luid_mapping_separates_devices(self):
        from resource_monitor import gpu_devices
        rows = [{'Name': 'pid_1_luid_0x00000000_0x00000001_phys_0_eng_0_engtype_Compute', 'UtilizationPercentage': 60},
                {'Name': 'pid_2_luid_0x00000000_0x00000002_phys_0_eng_0_engtype_Compute', 'UtilizationPercentage': 20}]
        devices = gpu_devices(rows, [{'id': 'luid_0x00000000_0x00000001', 'name': 'NVIDIA GeForce RTX 4060'},
                                     {'id': 'luid_0x00000000_0x00000002', 'name': 'Intel UHD Graphics'}])
        self.assertEqual([d['kind'] for d in devices], ['외장', '내장'])
        self.assertEqual([d['usage'] for d in devices], [60, 20])
