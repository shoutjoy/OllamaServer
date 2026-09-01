const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const crypto=require('node:crypto');
const html=fs.readFileSync('CHAT/ollama-say.html','utf8');
const helpers=html.slice(html.indexOf('    const GENERATION_DEFAULTS'),html.indexOf('    function loadGitHubConfig'));
const handler=html.slice(html.indexOf('      const handleSendMessage ='),html.indexOf('      const handleStop ='));
function setup(saved='{}'){
  const ctx={localStorage:{getItem:()=>saved}};
  vm.createContext(ctx);
  vm.runInContext(helpers+'\nthis.defaults=GENERATION_DEFAULTS;this.build=buildGenerationSettings;this.load=loadGenerationSettings;',ctx);
  return ctx;
}
test('blank options preserve server defaults, invalid limits are rejected',()=>{
  const c=setup();
  assert.equal(JSON.stringify(c.build(c.defaults,'llama3','instant')),JSON.stringify({options:{temperature:0.7}}));
  for(const patch of [{num_predict:0},{num_predict:-2},{num_ctx:2.5},{top_p:1.1},{top_k:-1},{seed:Infinity}]){
    assert.throws(()=>c.build({...c.defaults,...patch},'llama3','instant'));
  }
  assert.equal(c.build({...c.defaults,num_predict:-1},'llama3','instant').options.num_predict,-1);
});
test('thinking options distinguish boolean models and GPT-OSS effort',()=>{
  const c=setup();
  assert.equal(c.build(c.defaults,'qwen3','reasoning').think,true);
  assert.equal(c.build({...c.defaults,thinking:'off'},'qwen3','reasoning').think,false);
  assert.equal(c.build({...c.defaults,effort:'high'},'gpt-oss:20b','instant').think,'high');
  assert.throws(()=>c.build({...c.defaults,thinking:'off'},'gpt-oss:20b','instant'));
});
test('stored settings restore and corrupt settings safely fall back',()=>{
  assert.equal(setup('{"num_predict":"4096","temperature":0.4}').load().num_predict,'4096');
  for(const saved of ['broken','{"num_ctx":-5}'])assert.equal(setup(saved).load().num_ctx,'');
});
test('actual chat request sends configured options in every mode',async()=>{
  for(const mode of ['instant','reasoning','academic','search']){
    const c=setup();let body;
    Object.assign(c,{crypto,AbortController,TextDecoder,console,
      chatReady:true,inputText:'test',isGenerating:false,abortControllerRef:{current:null},followMessagesRef:{current:true},
      generationSettings:{...c.defaults,temperature:0.6,num_predict:'128',num_ctx:'4096',top_p:'0.8',top_k:'20',repeat_penalty:'1.1',seed:'42',thinking:'on',effort:'low'},
      selectedModel:'gpt-oss:20b',customModelInput:'',activeMode:mode,
      MODES:{[mode.toUpperCase()]:{systemPrompt:'test'}},systemPrompt:'',
      sessions:[{id:'1',messages:[]}],currentSessionId:'1',isDemoMode:false,connectionStatus:'connected',activeUrl:'http://localhost',
      setInputText:()=>{},setIsGenerating:()=>{},setActiveResponseId:()=>{},setSearchStatus:()=>{},showToast:message=>{throw Error(message);},
      setSessions:update=>{c.sessions=typeof update==='function'?update(c.sessions):update;},
      fetchAcademicPapers:async()=>[],fetchWebKnowledge:async()=>[],
      fetch:async(url,request)=>{body=JSON.parse(request.body);return {ok:true,body:{getReader:()=>({read:async()=>({done:true})})}};}
    });
    vm.runInContext(handler+'\nthis.send=handleSendMessage;',c);
    await c.send();
    assert.deepEqual(body.options,{temperature:0.6,num_predict:128,num_ctx:4096,top_p:0.8,top_k:20,repeat_penalty:1.1,seed:42});
    assert.equal(body.think,'low');
    assert.ok(!c.sessions[0].messages.some(m=>m.isError));
  }
});
