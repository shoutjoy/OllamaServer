const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

test('primary chat connects directly to loopback Ollama API',()=>{
  const html=fs.readFileSync('CHAT/ollama-say.html','utf8');
  assert.match(html,/const \[localUrl, setLocalUrl\] = useState\('http:\/\/127\.0\.0\.1:11434'\)/);
  assert.doesNotMatch(html,/location\.origin\s*\+\s*['"]\/ollama['"]/);
});

test('desktop server enables browser origins while remaining loopback-only',()=>{
  const source=fs.readFileSync('app.py','utf8');
  assert.match(source,/OLLAMA_HOST='127\.0\.0\.1:11434'/);
  assert.match(source,/OLLAMA_ORIGINS='\*'/);
});
