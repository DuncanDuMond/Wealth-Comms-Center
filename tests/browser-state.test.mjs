import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {test} from 'node:test';
import {messages, languages, translatedBody, translatedSign} from '../web/locales.js';

const source=(await readFile(new URL('../web/app.js',import.meta.url),'utf8'))
  .replace(/^import .*;\r?\n/, 'const languages={en:"English"},message=key=>key,translatedBody=value=>value,translatedSign=value=>value;\n')
  .replace(/boot\(\);\s*$/, '');
function setup() {
  const requests=[];
  const context=vm.createContext({navigator:{language:'en'},localStorage:{getItem:()=>null,setItem(){},removeItem(){}},Intl,Date,Set,Map,DOMException,AbortController,console,setTimeout,clearTimeout,
    fetch:()=>new Promise((resolve,reject)=>requests.push({resolve,reject})),
  });
  vm.runInContext(source,context);
  vm.runInContext('render=()=>{}; state.session={user:{id:"account-a",email:"a@example.test"}};',context);
  return {context,requests,run:code=>vm.runInContext(code,context)};
}
function response(value,status=200) {return {ok:status>=200&&status<300,status,json:async()=>value};}

test('all six locales contain every UI message, without fallback gaps',()=>{
  assert.deepEqual(Object.keys(languages),['en','ja','zh-CN','th','ko','vi']);
  const keys=Object.keys(messages.en).sort();
  for(const locale of Object.keys(languages)){
    assert.deepEqual(Object.keys(messages[locale]).sort(),keys,locale);
    for(const key of keys)assert.equal(typeof messages[locale][key],'string',`${locale}:${key}`);
  }
  assert.equal(translatedBody('Sun','ja'),'太陽');
  assert.equal(translatedBody('Lot of Fortune','zh-CN'),'福点');
  assert.equal(translatedSign('Ophiuchus','ko'),'뱀주인자리');
});

test('sign-out clears all private drafts, reports, locations and experiment results',()=>{
  const {run}=setup();
  run('state.followup={title:"PRIVATE-A",body:"PRIVATE-NOTE"};state.entryOpen=true;state.editing={name:"A"};state.equation={raw:123};state.equationInputs={capital:42};state.report={private:true};state.journal=[{body:"A"}];state.messages=[{text:"A"}];state.selectedPlace={latitude:12};clearPrivateState();');
  for(const key of ['followup','editing','equation','equationInputs','report','selectedPlace'])assert.equal(run(`state.${key}`),null,key);
  for(const key of ['journal','messages','profiles','compare'])assert.equal(run(`state.${key}.length`),0,key);
  assert.equal(run('state.entryOpen'),false);
  assert.equal(run('state.session.user'),null);
});

test('delayed old-account profile response is discarded after switching accounts',async()=>{
  const {run,requests}=setup();
  const pending=run('loadProfiles()');
  const rejection=assert.rejects(pending,{name:'AbortError'});
  run('clearPrivateState();state.session={user:{id:"account-b"}};state.profiles=[{id:"profile-b",name:"B"}];');
  requests[0].resolve(response([{id:'profile-a',name:'PRIVATE-A',birth_date:'1990-01-01'}]));
  await rejection;
  assert.equal(run('state.profiles[0].id'),'profile-b');
  assert.equal(run('state.profiles.length'),1);
});

test('late old-account unauthorized response cannot log out the new account',async()=>{
  const {run,requests}=setup();
  const pending=run('api("/api/profiles")');
  const rejection=assert.rejects(pending,{name:'AbortError'});
  run('clearPrivateState();state.session={user:{id:"account-b"}};');
  requests[0].resolve(response({detail:'Unauthorized'},401));
  await rejection;
  assert.equal(run('state.session.user.id'),'account-b');
});

test('account switch while parsing response body also discards old private data',async()=>{
  const {run,requests}=setup();
  let resolveBody;
  const body=new Promise(resolve=>{resolveBody=resolve;});
  const pending=run('api("/api/profiles")');
  const rejection=assert.rejects(pending,{name:'AbortError'});
  requests[0].resolve({ok:true,status:200,json:()=>body});
  await Promise.resolve();await Promise.resolve();
  run('clearPrivateState();state.session={user:{id:"account-b"}};');
  resolveBody([{id:'profile-a',name:'PRIVATE-A'}]);
  await rejection;
  assert.equal(run('state.session.user.id'),'account-b');
});

test('UI contracts preserve field limits, consent default, and selected report date',()=>{
  const {run}=setup();
  run('state.session={user:{id:"account-a"},ai_enabled:true};state.profileId="p1";');
  assert.match(run('profileForm()'),/name="name" required maxlength="100"/);
  assert.match(run('journalForm()'),/name="outcome" maxlength="5000"/);
  const consent=run('agentView()').match(/<input name="use_cloud_ai"[^>]+>/)?.[0];
  assert.ok(consent);
  assert.ok(!consent.includes('checked'));
  assert.match(source,/report_date:state\.reportDate/);
});

test('service worker never intercepts private APIs or page navigations',async()=>{
  const handlers={};
  const context=vm.createContext({self:{location:{origin:'https://wealth.test'},addEventListener:(name,handler)=>handlers[name]=handler},URL,fetch:()=>{throw new Error('not expected');},caches:{}});
  vm.runInContext(await readFile(new URL('../web/sw.js',import.meta.url),'utf8'),context);
  for(const path of ['/api/session','/api/profiles','/api/agent','/']){
    let intercepted=false;
    handlers.fetch({request:{method:'GET',url:'https://wealth.test'+path},respondWith(){intercepted=true;}});
    assert.equal(intercepted,false,path);
  }
});
