const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const {test}=require('node:test');
const html=readFileSync(__dirname+'/ollama-say.html','utf8');
const source=html.slice(html.indexOf('    function loadGitHubConfig'),html.indexOf('    async function restoreDocuments'));
function setup(responses,confirm=true){
  const calls=[];
  const ctx={TextEncoder,AbortSignal,btoa,window:{confirm:()=>confirm},localStorage:{getItem:()=>null},fetch:async(url,options)=>{calls.push({url,options});const r=responses.shift();assert.ok(r,'unexpected request');return {ok:r.status<400,status:r.status,json:async()=>r.data};}};
  vm.createContext(ctx);vm.runInContext(source,ctx);return {ctx,calls};
}
const config={repo:'https://github.com/owner/repo.git',token:'test-only-token',branch:''};
const metadata=()=>[{status:200,data:{login:'owner'}},{status:200,data:{default_branch:'main'}},{status:200,data:{name:'main'}}];
test('new UTF-8 document creates a commit on the resolved branch',async()=>{
  const {ctx,calls}=setup([...metadata(),{status:404,data:{}},{status:201,data:{commit:{sha:'abc'}}}]);
  await ctx.commitGitHubDocument(config,{text:'한글 수식 $x$'},'docs/문서.md','문서 저장');
  const request=calls.at(-1);assert.equal(request.options.method,'PUT');
  const body=JSON.parse(request.options.body);assert.equal(Buffer.from(body.content,'base64').toString(),'한글 수식 $x$');assert.equal(body.branch,'main');assert.equal(body.sha,undefined);
});
test('existing file uses exact remote SHA and reports conflict without retry',async()=>{
  const {ctx,calls}=setup([...metadata(),{status:200,data:{type:'file',sha:'old-sha'}},{status:409,data:{}}]);
  await assert.rejects(ctx.commitGitHubDocument(config,{text:'update'},'doc.md','update'),/변경/);
  assert.equal(JSON.parse(calls.at(-1).options.body).sha,'old-sha');assert.equal(calls.length,5);
});
test('cancel causes no external write',async()=>{
  const {ctx,calls}=setup([...metadata(),{status:404,data:{}}],false);
  assert.equal(await ctx.commitGitHubDocument(config,{text:'x'},'doc.md','update'),null);
  assert.ok(calls.every(c=>!c.options.method));
});
test('private repository 404 is not silently treated as an empty repository',async()=>{
  const {ctx,calls}=setup([{status:200,data:{login:'owner'}},{status:404,data:{}}]);
  await assert.rejects(ctx.commitGitHubDocument(config,{text:'x'},'doc.md','update'),/권한/);assert.equal(calls.length,2);
});
test('token stays out of persistent config and backup export',()=>{
  assert.match(html,/JSON\.stringify\(\{repo:next\.repo,branch:next\.branch\}\)/);
  assert.match(html,/documents:rows\.map\(\(\{id,title,text,updated\}\)/);
});
test('each message has a unique ID for stream updates and per-answer source views',()=>{
  assert.match(html,/const userMsg = \{\s+id: crypto.randomUUID\(\)/);
  assert.match(html,/const assistantMsg = \{\s+id: crypto.randomUUID\(\)/);
});
test('workspace starts collapsed and remains mounted to preserve editing state',()=>{
  assert.match(html,/\[isWorkspaceOpen,setIsWorkspaceOpen\]=useState\(false\)/);
  assert.match(html,/style=\{\{display:isOpen\?undefined:'none'\}\}/);
  assert.match(html,/aria-label="문서 작업실 열기"/);
  assert.match(html,/aria-label="문서 작업실 닫기"/);
  assert.match(html,/<EditorPanel[^>]*isOpen=\{isWorkspaceOpen\}/);
  assert.match(html,/insertRef.current=text=>\{[^\n]*onOpen\(\)/);
});
