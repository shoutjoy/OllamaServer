const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const html=fs.readFileSync('CHAT/ollama-say.html','utf8');
const start=html.indexOf('    function normalizeMermaidSource(');
const end=html.indexOf('    let diagramQueue=',start);
const context={};
vm.createContext(context);
vm.runInContext(html.slice(start,end)+'\nthis.normalizeMermaidSource=normalizeMermaidSource;',context);

test('plain Mermaid node labels are safely quoted',()=>{
  const source='graph TD\n A[뇌가소성 (Neuroplasticity)] --> B{핵심 능력};\n B --> C[경험 / 환경: 반응];';
  const result=context.normalizeMermaidSource(source);
  assert.match(result,/A\["뇌가소성 \(Neuroplasticity\)"\]/);
  assert.match(result,/B\{"핵심 능력"\}/);
  assert.match(result,/C\["경험 \/ 환경: 반응"\]/);
});

test('already quoted labels, edges, and style declarations stay intact',()=>{
  const source='graph TD\n A["이미 안전함"] --> B[대상]\n style A fill:#ADD8C,stroke:#333';
  const result=context.normalizeMermaidSource(source);
  assert.match(result,/A\["이미 안전함"\]/);
  assert.doesNotMatch(result,/A\[""이미 안전함""\]/);
  assert.match(result,/A\["이미 안전함"\] --> B\["대상"\]/);
  assert.match(result,/style A fill:#ADD8C,stroke:#333/);
});

test('compound flowchart shapes are quoted without changing delimiters',()=>{
  const source='flowchart LR\n A[[서브루틴 / 작업]] --> B([시작과 끝]) --> C{{조건 (검사)}}';
  assert.equal(context.normalizeMermaidSource(source),'flowchart LR\n A[["서브루틴 / 작업"]] --> B(["시작과 끝"]) --> C{{"조건 (검사)"}}');
});
