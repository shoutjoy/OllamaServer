const fs = require('node:fs');
const assert = require('node:assert/strict');

const html = fs.readFileSync('CHAT/ollama-say.html', 'utf8');

assert.match(html, /api\.openalex\.org\/works\?search=.*per_page=\$\{perSource\}/);
assert.match(html, /api\.crossref\.org\/works\?query=.*rows=\$\{perSource\}/);
assert.match(html, /export\.arxiv\.org\/api\/query\?search_query=all:/);
assert.match(html, /Promise\.allSettled\(\[openAlexTask, crossrefTask, arxivTask\]\)/);
assert.doesNotMatch(html, /if \(papers\.length < 3\)/);
assert.match(html, /paper\.source/);
for (const value of ['10', '120', '30', '50', '100']) {
  assert.match(html, new RegExp(`<option value="${value}">${value}<\\/option>`));
}
assert.match(html, /학술검색 직접 입력 개수/);
assert.match(html, /모든 답변은 전문적인 한국어 학술 문체로 작성한다/);

console.log('PASS: all academic providers, count controls, and default academic writing style are wired');
