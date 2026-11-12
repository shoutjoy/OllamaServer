"""Preload via the same API and runtime options used by chat."""
from core import chat_performance


def run_ollama_model(executable, client, model, settings, output):
    # executable is retained for existing callers; no CLI process is needed.
    if settings.get('keep_alive') == '0':
        raise ValueError('모델 유지 시간이 0이면 즉시 해제됩니다. 로딩하려면 5분 이상을 선택하세요.')
    output('> Ollama API 모델 준비: ' + model + '\n')
    request = {'model': model, 'stream': False}
    request.update(chat_performance(settings, model))
    result = client.post('/api/generate', request)
    if result.get('done') is not True:
        raise RuntimeError('모델 로딩 완료 응답을 받지 못했습니다.')
    return model in client.safe_draft_models
