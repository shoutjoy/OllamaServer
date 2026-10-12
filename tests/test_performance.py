import unittest
from core import model_placement, PERFORMANCE_DEFAULTS, validate_performance, performance_environment, chat_performance


class PerformanceTests(unittest.TestCase):
    def test_environment_covers_server_options(self):
        settings = dict(PERFORMANCE_DEFAULTS, keep_alive='30m', flash_attention=True, kv_cache_type='q8_0')
        env = performance_environment(settings)
        self.assertEqual(env['OLLAMA_KEEP_ALIVE'], '30m')
        self.assertEqual(env['OLLAMA_CONTEXT_LENGTH'], '4096')
        self.assertEqual(env['OLLAMA_NUM_PARALLEL'], '1')
        self.assertEqual(env['OLLAMA_FLASH_ATTENTION'], '1')
        self.assertEqual(env['OLLAMA_KV_CACHE_TYPE'], 'q8_0')

    def test_invalid_input_and_cache_dependency(self):
        for values in ({'context_length': 0}, {'num_parallel': '1.5'}, {'num_predict': -1},
                       {'keep_alive': 'bad'}, {'kv_cache_type': 'q8_0'}, {'flash_attention': 'false'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_performance(values)

    def test_chat_options_and_gpt_oss_thinking(self):
        request = chat_performance({'thinking': 'off', 'num_predict': 1024}, 'qwen3:8b')
        self.assertIs(request['think'], False)
        self.assertEqual(request['options'], {'num_ctx': 4096, 'num_predict': 1024})
        self.assertEqual(chat_performance({'thinking': 'off'}, 'gpt-oss:20b')['think'], 'low')
        self.assertNotIn('think', chat_performance({}, 'qwen3:8b'))

    def test_defaults_are_not_mutated(self):
        validate_performance({'num_predict': 100})
        self.assertEqual(PERFORMANCE_DEFAULTS['num_predict'], 4096)


class IntegratedGpuTests(unittest.TestCase):
    def test_gpu_enable_environment_and_old_settings(self):
        env = performance_environment({'integrated_gpu': True})
        self.assertEqual(env['OLLAMA_IGPU_ENABLE'], '1')
        self.assertEqual(env['OLLAMA_VULKAN'], '1')
        self.assertEqual(env['OLLAMA_MAX_LOADED_MODELS'], '1')
        self.assertNotIn('OLLAMA_IGPU_ENABLE', performance_environment({}))
        self.assertFalse(validate_performance({})['integrated_gpu'])

    def test_partial_offload_and_auto(self):
        self.assertEqual(chat_performance({'num_gpu': 2}, 'llama3.2:1b')['options']['num_gpu'], 2)
        self.assertEqual(chat_performance({'num_gpu': 0}, 'llama3.2:1b')['options']['num_gpu'], 0)
        self.assertNotIn('num_gpu', chat_performance({}, 'llama3.2:1b')['options'])
        for settings in ({'num_gpu': -2}, {'max_loaded_models': 0}, {'integrated_gpu': '1'}):
            with self.assertRaises(ValueError):
                validate_performance(settings)

    def test_placement_is_model_memory_not_gpu_busy_percent(self):
        self.assertIn('모델 미로드', model_placement([]))
        model = {'name': 'small', 'size': 100, 'size_vram': 0, 'details': {'quantization_level': 'Q4_K_M'}}
        self.assertIn('CPU 배치', model_placement([model]))
        model['size_vram'] = 40
        self.assertIn('CPU + GPU', model_placement([model]))
        model['size_vram'] = 100
        self.assertIn('GPU 배치', model_placement([model]))
