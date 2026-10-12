import unittest
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
            self.assertIsNone(sampler.sample()['gpu'])
