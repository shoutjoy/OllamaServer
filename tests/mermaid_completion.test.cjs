const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('CHAT/ollama-say.html','utf8');
const start=html.indexOf('    function Markdown(');
const component=html.slice(start,html.indexOf('      return <div className="md-content"',start))+'}\nthis.Markdown=Markdown;';

function harness(){
  const state={jobs:new Map(),renders:[],html:'',cleanup:null};
  let id=0;
  const context={
    useState:()=>['',value=>{state.html=value;}],
    useEffect:(effect,deps)=>{state.cleanup=effect();state.deps=deps;},
    markdownHtml:text=>'source:'+text,
    richMarkdownHtml:async text=>{state.renders.push(text);return 'svg:'+text;},
    setTimeout:fn=>{state.jobs.set(++id,fn);return id;},
    clearTimeout:key=>state.jobs.delete(key)
  };
  vm.createContext(context);vm.runInContext(component,context);
  state.update=(text,renderDiagrams,theme)=>{state.cleanup?.();context.Markdown({text,renderDiagrams,theme});};
  state.flush=async()=>{for(const job of state.jobs.values())job();state.jobs.clear();await Promise.resolve();};
  return state;
}
test('even a complete fence stays source during streaming, then renders without another text chunk',async()=>{
  const h=harness();const text='```mermaid\nflowchart LR\n A-->B\n```';
  h.update(text,false);await h.flush();
  assert.deepEqual(h.renders,[]);assert.equal(h.html,'source:'+text);
  h.update(text,true);await h.flush();
  assert.deepEqual(h.renders,[text]);assert.equal(h.html,'svg:'+text);
  assert.deepEqual(Array.from(h.deps),[text,true,'dark']);
});
test('an obsolete pending diagram is cancelled before another stream update',async()=>{
  const h=harness();h.update('old',true);h.update('partial',false);await h.flush();
  assert.deepEqual(h.renders,[]);assert.equal(h.html,'source:partial');
});
test('editor preview retains diagram rendering by default',async()=>{
  const h=harness();h.update('preview');await h.flush();
  assert.deepEqual(h.renders,['preview']);
});
test('theme changes trigger a fresh diagram render',async()=>{
  const h=harness();h.update('diagram',true,'dark');await h.flush();
  h.update('diagram',true,'light');await h.flush();
  assert.deepEqual(h.renders,['diagram','diagram']);
  assert.deepEqual(Array.from(h.deps),['diagram',true,'light']);
});
