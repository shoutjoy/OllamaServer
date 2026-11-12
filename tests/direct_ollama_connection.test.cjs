const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

test('manager chat uses optimized proxy and standalone chat retains direct endpoint',()=>{
  const html=fs.readFileSync('CHAT/ollama-say.html','utf8');
  assert.ok(html.includes("window.location.port === '8767' ? window.location.origin + '/ollama' : 'http://127.0.0.1:11434'"));
  assert.ok(html.includes('const [localUrl, setLocalUrl] = useState(managerEndpoint)'));
});

test('desktop server enables browser origins while remaining loopback-only',()=>{
  const source=fs.readFileSync('app.py','utf8');
  assert.match(source,/OLLAMA_HOST='127\.0\.0\.1:11434'/);
  assert.match(source,/OLLAMA_ORIGINS='\*'/);
});
