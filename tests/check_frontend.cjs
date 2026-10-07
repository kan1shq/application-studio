// Functional render/save contract checks without a browser or visual QA.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),read=n=>JSON.parse(fs.readFileSync(path.join(root,'data',n),'utf8'));
const elements=new Map();
function element(key){if(!elements.has(key))elements.set(key,{innerHTML:'',insertAdjacentHTML(where,html){this.innerHTML+=html},textContent:'',value:'',style:{},dataset:{},classList:{toggle(){}},focus(){},setSelectionRange(){},showModal(){},close(){},click(){}});return elements.get(key)}
const sample={jobs:read('jobs_seed.json').jobs.map(j=>({...j,application_status:'New',notes:''})),plan:read('plan.json'),analysis:read('analysis.json'),companies:read('companies.json'),sources:read('sources.json'),prep_state:{},refresh:{running:false,message:'Ready'}};
sample.curriculum={items:[{id:'dsa:lc-1',title:'Test problem',kind:'dsa',placement:'core',assigned_days:[1],source_urls:['https://example.com/problem'],resource_ids:[],prerequisite_ids:[]}],resources:[],source_inventory:[{source_url:'https://example.com'}]};sample.learning={states:{},attempts:[],retries:[],snapshots:[],adoptions:[]};
let saves=[],learningWrites=[],failLearning=false;
const sandbox={console,URL,URLSearchParams,Blob,structuredClone,setTimeout,clearTimeout,setInterval,clearInterval,localStorage:{getItem(){return null},setItem(){}},document:{querySelector:element,querySelectorAll(){return []},createElement(){return element('created')}},fetch:async(url,options)=>{if(options?.method==='POST'){const body=JSON.parse(options.body);if(url==='/api/prep-state'){await new Promise(r=>setTimeout(r,15));saves.push(body)}return {ok:true,json:async()=>({saved:true})}}return {ok:true,json:async()=>structuredClone(sample)}}};
const baseFetch=sandbox.fetch;sandbox.fetch=async(url,options)=>{if(url==='/api/resume/profile')return {ok:true,json:async()=>({profile:null})};if(url==='/api/resume/gaps')return {ok:true,json:async()=>({jobs_scanned:1,prospects:0,full_jd_count:0,priority_gaps:[],jobs:[],profile_source:'Synthetic test'})};if(options?.method==='POST'&&url.startsWith('/api/learning/')){learningWrites.push(JSON.parse(options.body));await new Promise(r=>setTimeout(r,15));if(failLearning)return {ok:false,json:async()=>({error:'Evidence save failed'})};sample.learning.states['dsa:lc-1']={...learningWrites.at(-1),version:1};return {ok:true,json:async()=>({saved:true})}}return baseFetch(url,options)};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(root,'dist/linkedin.js'),'utf8'),sandbox);vm.runInContext(fs.readFileSync(path.join(root,'dist/learning.js'),'utf8'),sandbox);vm.runInContext(fs.readFileSync(path.join(root,'dist/resume.js'),'utf8'),sandbox);vm.runInContext(fs.readFileSync(path.join(root,'dist/app.js'),'utf8'),sandbox);
(async()=>{
await new Promise(r=>setTimeout(r,20));
for(const name of ['jobs','linkedin','discovery','prep','projects','study','materials','learning','curriculum','gaps','resume','companies','sources']){vm.runInContext(`tab='${name}';render()`,sandbox);assert(element('#app').innerHTML.length>100,`${name} did not render`)}
vm.runInContext("tab='prep';day=1;render()",sandbox);assert(element('#app').innerHTML.includes('data-learning-item="dsa:lc-1"'),'Daily prep shared item missing');
vm.runInContext("openLearningItem('dsa:lc-1')",sandbox);assert(element('#detail-body').innerHTML.includes('Record a practice attempt'),'DSA attempt form missing');assert(element('#detail-body').innerHTML.includes('https://example.com/problem'),'Source link missing');
vm.runInContext("state.curriculum.items[0].source_outline={headings:['Study heading'],steps:['Explain the invariant']};state.curriculum.items[0].acceptance=['Observable proof'];openLearningItem('dsa:lc-1')",sandbox);assert(element('#detail-body').innerHTML.includes('Study heading'));assert(element('#detail-body').innerHTML.includes('Observable proof'));
vm.runInContext("state.learning.adoptions=[{id:'adopted:1',title:'Adopted reference',url:'https://example.com/ref'}];state.curriculum.items.push({id:'checkpoint:1',kind:'checkpoint',title:'Readiness',evidence_ids:['dsa:lc-1']});openLearningItem('checkpoint:1')",sandbox);assert(element('#detail-body').innerHTML.includes('Checkpoint evidence review'),'Checkpoint linked evidence missing');assert.equal(vm.runInContext("curriculum().items.find(i=>i.id==='adopted:1').placement",sandbox),'reference');
vm.runInContext("state.learning.adoptions.push({id:'dsa:lc-1',title:'Updated catalog lesson',url:'https://example.com/updated',access:'mixed',summary:'Updated source notes'});openLearningItem('dsa:lc-1')",sandbox);assert(element('#detail-body').innerHTML.includes('Updated catalog lesson'));assert.equal(vm.runInContext("curriculum().items.find(i=>i.id==='dsa:lc-1').placement",sandbox),'core');assert.equal(vm.runInContext("curriculum().items.find(i=>i.id==='dsa:lc-1').assigned_days[0]",sandbox),1);
vm.runInContext("state.curriculum.items.push(...Array.from({length:65},(_,n)=>({id:'reference:'+n,title:'Reference '+n,kind:'reference',placement:'reference'})));tab='learning';render()",sandbox);assert.equal((element('#app').innerHTML.match(/<article class="card">/g)||[]).length,50,'Learning map pagination missing');element('#learning-next').onclick();assert(element('#app').innerHTML.includes('page 2'),'Next learning page did not render');
failLearning=true;element('#learning-notes').value='Keep my draft';await vm.runInContext("saveLearning('/api/learning/state',{id:'dsa:lc-1',status:'studied',version:0},'dsa:lc-1')",sandbox);assert.equal(element('#learning-notes').value,'Keep my draft');assert.equal(element('#learning-error').textContent,'Evidence save failed');assert.equal(vm.runInContext("learningStatus('dsa:lc-1')",sandbox),'not_started');
failLearning=false;learningWrites=[];await vm.runInContext("Promise.all([saveLearning('/api/learning/state',{id:'dsa:lc-1',status:'studied',version:0},'dsa:lc-1'),saveLearning('/api/learning/state',{id:'dsa:lc-1',status:'demonstrated',version:0},'dsa:lc-1')])",sandbox);assert.equal(learningWrites.length,1,'Concurrent evidence writes were not disabled');assert.equal(vm.runInContext("learningStatus('dsa:lc-1')",sandbox),'studied');
vm.runInContext("tab='linkedin';render()",sandbox);
assert(element('#app').innerHTML.includes('Page limit'),'LinkedIn pagination control missing');
element('#li-pages').onchange({target:{value:'3'}});
assert.equal(vm.runInContext('linkedinConfig().pages',sandbox),3);
vm.runInContext("tab='study';render()",sandbox);
assert(element('#app').innerHTML.includes('2023-04-01'),'Historical company-list warning missing');
assert(element('#app').innerHTML.includes('Minimum Window Substring'),'Curated DSA list missing');
vm.runInContext("tab='projects';render()",sandbox);
assert(element('#app').innerHTML.includes('Where did my disk space actually go?'),'Approved project missing');
assert(!element('#app').innerHTML.includes('FootballWorkbench'),'Rejected flagship still displayed');
vm.runInContext("tab='prep';day=140;render()",sandbox);
assert(element('#app').innerHTML.includes('140'),'Last extension day is missing');
vm.runInContext("tab='materials';render()",sandbox);
assert(element('#app').innerHTML.includes('MCP'),'Modern resources missing');
assert.equal(vm.runInContext("exerciseStartDay('W11Ã¢â‚¬â€œ12')",sandbox),71);
assert.equal(vm.runInContext("exerciseStartDay('Elective')",sandbox),null);
vm.runInContext("tab='prep';day=1;render();var firstSave=savePrep({...dayState(1),tasks:[0]});var secondSave=savePrep({...dayState(1),tasks:[...dayState(1).tasks,1]});day=2;renderPrep()",sandbox);
await vm.runInContext('Promise.all([firstSave,secondSave])',sandbox);
assert.deepEqual(saves.map(x=>x.day),[1,1]);assert.deepEqual(saves.map(x=>x.state.tasks),[[0],[0,1]]);
assert.equal(vm.runInContext('day',sandbox),2);assert.equal(vm.runInContext('state.prep_state["2"]',sandbox),undefined);
assert.equal(vm.runInContext('state.prep_state["1"].tasks.length',sandbox),2);
console.log('PASS: all tabs (including resume and live gaps) and day140 render; materials and LinkedIn search appear; rapid saves serialize without cross-day corruption.');
})().catch(e=>{console.error(e);process.exitCode=1});
