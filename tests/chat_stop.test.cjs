const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('CHAT/ollama-say.html', 'utf8');
const handler = html.slice(html.indexOf('      const handleSendMessage ='), html.indexOf('      const handleNewChat ='));
assert.ok(handler.includes('controller.signal'));
assert.equal((html.match(/ReactDOM.createRoot/g) || []).length, 1);

async function scenario(mode) {
  let state;
  let signal;
  let requests = 0;
  const waiting = (s) => {
    signal = s;
    requests++;
    return new Promise((resolve, reject) => {
      s.addEventListener('abort', () => reject(new DOMException('Stopped', 'AbortError')), { once: true });
    });
  };
  state = {
    AbortController, DOMException, TextDecoder, console,
    inputText: '중지 테스트', isGenerating: false,
    selectedModel: 'test', customModelInput: '', activeMode: mode,
    MODES: { [mode.toUpperCase()]: { systemPrompt: 'test' } },
    sessions: [{ id: '1', messages: [] }], currentSessionId: '1',
    isDemoMode: false, connectionStatus: 'connected', activeUrl: 'http://localhost', temperature: 0.7,
    abortControllerRef: { current: null },
    setInputText: value => { state.inputText = value; },
    setSessions: value => { state.sessions = typeof value === 'function' ? value(state.sessions) : value; },
    setIsGenerating: value => { state.isGenerating = value; },
    setSearchStatus: value => { state.searchStatus = value; },
    showToast: value => { state.toast = value; },
    fetch: (_, options) => waiting(options.signal),
    fetchAcademicPapers: (_, s) => waiting(s),
    fetchWebKnowledge: (_, s) => waiting(s),
  };
  vm.createContext(state);
  vm.runInContext(handler + '\nthis.send = handleSendMessage; this.stop = handleStop;', state);
  let work = state.send();
  assert.equal(state.isGenerating, true);
  state.stop();
  assert.equal(signal.aborted, true);
  state.inputText = '아직 정리 중';
  await state.send();
  assert.equal(requests, 1, 'must not overlap requests while cancellation unwinds');
  await work;
  assert.equal(state.isGenerating, false);
  assert.equal(state.abortControllerRef.current, null);
  assert.ok(!state.sessions[0].messages.some(m => m.isError));
  assert.ok(state.toast.includes('중지'));
  state.inputText = '다시 전송';
  work = state.send();
  assert.equal(requests, 2);
  state.stop();
  await work;
}

(async () => {
  for (const mode of ['instant', 'academic', 'search']) await scenario(mode);
  console.log('PASS: cancel waiting response / academic / web search, no overlapping send, resend after stop');
})().catch(error => { console.error(error); process.exitCode = 1; });
