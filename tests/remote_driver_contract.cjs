// Original behavior mock for the Cubase DirectAccess API; no Steinberg runtime included.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const driverFile=process.argv[2];
function fixture(api13=true) {
 const params={10:{1:{value:.8,title:'Volume',unit:'dB'}},20:{1:{value:.6,title:'Volume',unit:'dB'}},15:{100:{value:.5,title:'Threshold',unit:'dB'}}};
 const nodes={0:{uid:'root',name:'VST Mixer',title:'Mixer',children:[10,20]},10:{uid:'kick-uid',name:'Audio',title:'Kick',children:[11]},20:{uid:'vocal-uid',name:'Audio',title:'Vocal',children:[]},11:{uid:'inserts-uid',name:'Inserts',title:'Inserts',children:[13,14]},13:{uid:'slot0-uid',name:'Slot',title:'Slot 1',children:[15]},14:{uid:'slot1-uid',name:'Slot',title:'Slot 2',children:[]},15:{uid:'compressor-uid',name:'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB-1',title:'Compressor',children:[]}};
 let writes=0,pluginWrites=0;const outgoing=[];
 const p=(id,tag)=>{if(!params[id]||!params[id][tag])throw Error('unknown parameter');return params[id][tag]};
 const da={activate(){},deactivate(){},update(){},getBaseObjectID:()=>0,getNumberOfChildObjects:(m,id)=>nodes[id].children.length,getChildObjectID:(m,id,i)=>nodes[id].children[i],getObjectUniqueIDString:(m,id)=>nodes[id].uid,getObjectUniqueName:(m,id)=>nodes[id].name,getObjectTitle:(m,id)=>nodes[id].title,getNumberOfParameters:(m,id)=>Object.keys(params[id]||{}).length,getParameterTagByIndex:(m,id,i)=>Number(Object.keys(params[id]||{})[i]),getParameterProcessValue:(m,id,t)=>p(id,t).value,getParameterDisplayValue:(m,id,t)=>(p(id,t).value*60-60).toFixed(2)+' dB',getParameterTitle:(m,id,t)=>p(id,t).title,getParameterDisplayUnits:(m,id,t)=>p(id,t).unit,getParameterEditLockState:(m,id,t)=>!!p(id,t).locked,setParameterEditLockState:(m,id,t,s)=>{p(id,t).locked=s},setParameterProcessValue:(m,id,t,value)=>{writes++;p(id,t).value=value}};
 if(api13){da.convertParameterPlainToProcessValue=(m,id,t,v)=>(v+60)/60;da.convertParameterProcessValueToPlain=(m,id,t,v)=>v*60-60;da.getParameterProcessValueType=()=> 'float';da.isParameterAutomatable=()=>true;da.mPluginManager={getNumberOfPluginCollections:()=>1,getIndexOfActivePluginCollection:()=>0,getIndexOfDefaultPluginCollection:()=>0,getPluginCollectionByIndex:()=>({mEntries:[{mPluginUID:'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',mPluginName:'Test EQ',mPluginVendor:'Mock',mPluginVersion:'1'}]}),trySetSlotPlugin:(m,id,uid)=>{pluginWrites++;if(nodes[id].children.length)throw Error('not empty');nodes[99]={uid:'new-plugin',name:uid+'-1',title:'Test EQ',children:[]};nodes[id].children=[99];return true}}}
 const commands=[];
 const input={},output={sendMidi:(d,data)=>outgoing.push(data)};
 const page={makeCommandBinding(trigger,category,name){trigger.command=[category,name]},mHostAccess:{mMixConsole:{makeMixerBankZone:()=>({})},makeDirectAccess:()=>da}};
 const driver={mSurface:{makeCustomValueVariable(){return {setProcessValue(device,v){if(v===1)commands.push(this.command)}}}},mPorts:{makeMidiInput:()=>input,makeMidiOutput:()=>output},makeDetectionUnit:()=>({detectPortPair:()=>({expectInputNameEquals(){},expectOutputNameEquals(){}})}),mMapping:{makePage:()=>page}};
 const context={require:name=>{assert.equal(name,'midiremote_api_v1');return {makeDeviceDriver:()=>driver,mDefaults:{mAppVersion:{getVersionString:()=>api13?'15.0.30':'15.0.10'}}}},console};
 vm.runInNewContext(fs.readFileSync(driverFile,'utf8'),context,{filename:driverFile});
 page.mOnActivate({},{});
 let serial=1;
 function request(op,args={},session,requestID){
  const id=requestID||String(serial++).padStart(32,'0');
  const body=JSON.stringify({id,op,args,session}).replace(/[\u007f-\uffff]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
  const total=Math.ceil(body.length/180),stream=serial+100;
  for(let i=0;i<total;i++)input.mOnSysex({},[240,125,67,77,65,1,stream&127,(stream>>7)&127,(stream>>14)&127,i&127,(i>>7)&127,total&127,(total>>7)&127,...Buffer.from(body.slice(i*180,(i+1)*180),'ascii'),247]);
  for(let i=0;i<200;i++)page.mOnIdle({});
  const parts=outgoing.splice(0).map(frame=>({i:frame[9]+(frame[10]<<7),body:String.fromCharCode(...frame.slice(13,-1))})).sort((a,b)=>a.i-b.i);
  const reply=JSON.parse(parts.map(x=>x.body).join(''));
  assert.equal(reply.id,id);return reply;
 }
 const hello=request('hello').result;
 return {request:(op,args,id)=>request(op,args,hello.session,id),raw:request,hello,nodes,params,page,commands,get writes(){return writes},get pluginWrites(){return pluginWrites},wire(data){input.mOnSysex({},data);for(let i=0;i<200;i++)page.mOnIdle({});return outgoing.splice(0)}};
}
if(process.argv[3]==='--wire') {
 const bridge=fixture();
 const lines=require('readline').createInterface({input:process.stdin});
 lines.on('line',line=>process.stdout.write(JSON.stringify(bridge.wire(JSON.parse(line)))+'\n'));
} else {
let f=fixture();
assert(f.hello.capabilities.physical_conversion);
assert(f.request('audio_command',{action:'render_selection'}).ok);
assert.deepEqual(f.commands,[['Render in Place','Render']]);
assert(!f.request('audio_command',{action:'unknown'}).ok);
f.nodes[0].children.push(10);
const channels=f.request('tracks').result.tracks;
assert.equal(channels.length,2);
f.params[10][2]={value:-1,title:'Other',unit:''};
assert.equal(f.request('channel_fader',{target:channels[0]}).result.parameter.plain,-12);
assert.equal(f.request('inspect',{target:channels[0]}).result.parameters[1].error,'INVALID_HOST_VALUE');
f.nodes[20].uid=f.nodes[10].uid;
assert(!f.request('channel_fader',{target:channels[0]}).ok);
f=fixture();
let t=f.request('tracks').result.tracks.find(x=>x.title==='Kick');
let large=f.request('preview',{target:t,object_id:10,parameter_tag:1,after:-17,value_kind:'channel_db',unit:'dB',max_delta:5});
assert(large.ok);assert.equal(large.result.plan.after_plain,-17);
assert(!f.request('preview',{target:t,object_id:15,parameter_tag:100,after:-35,value_kind:'channel_db',unit:'dB',max_delta:5}).ok);
let inspected=f.request('inspect',{target:t,object_id:10}).result;
assert.equal(inspected.parameters[0].unit,'dB');assert.equal(inspected.parameters[0].plain,-12);
let plan=f.request('preview',{target:t,object_id:10,parameter_tag:1,after:-13,value_kind:'plain',unit:'dB',max_delta:1}).result.plan;
assert.equal(f.writes,0);
// Selection is not part of the address: target identity identifies Kick directly.
f.nodes[0].children=[20,10];
assert(f.request('apply',{plan},'a'.repeat(32)).ok);assert.equal(f.writes,1);assert.equal(f.params[20][1].value,.6);
assert(!f.request('apply',{plan},'a'.repeat(32)).ok);assert.equal(f.writes,1);
assert.equal(f.request('read',{plan}).result.parameter.normalized,plan.after_normalized);
assert(!f.request('preview',{target:t,object_id:20,parameter_tag:1,after:.5,value_kind:'normalized',max_delta:.1}).ok);
f=fixture();t=f.request('tracks').result.tracks[0];plan=f.request('preview',{target:t,object_id:15,parameter_tag:100,after:.45,value_kind:'normalized',max_delta:.1}).result.plan;
f.nodes[15].uid='replaced-plugin';assert(!f.request('apply',{plan}).ok);assert.equal(f.writes,0);
f=fixture();t=f.request('tracks').result.tracks[0];plan=f.request('preview',{target:t,object_id:10,parameter_tag:1,after:.75,value_kind:'normalized',max_delta:.1}).result.plan;
f.params[10][1].value=.7;assert(!f.request('apply',{plan}).ok);assert.equal(f.writes,0);
f.params[10][1].value=.8;f.params[10][1].locked=true;assert(!f.request('apply',{plan}).ok);assert.equal(f.writes,0);
f.params[10][1].locked=false;f.page.mOnDeactivate({},{});f.page.mOnActivate({},{});assert(!f.raw('apply',{plan},f.hello.session).ok);assert.equal(f.writes,0);
f=fixture();t=f.request('tracks').result.tracks[0];assert(!f.request('preview_plugin',{target:t,object_id:13,plugin_uid:'A'.repeat(32)}).ok);
assert(!f.request('preview_plugin',{target:t,object_id:14,plugin_uid:'C'.repeat(32)}).ok);
plan=f.request('preview_plugin',{target:t,object_id:14,plugin_uid:'A'.repeat(32)}).result.plan;
assert.equal(f.pluginWrites,0);assert(f.request('apply_plugin',{plan}).ok);assert.equal(f.pluginWrites,1);
assert(f.request('inspect',{target:t,object_id:14}).result.children[0].unique_name.startsWith('A'.repeat(32)));
f=fixture(false);t=f.request('tracks').result.tracks[0];assert(!f.hello.capabilities.physical_conversion);assert(!f.request('plugins',{target:t,object_id:14}).ok);
assert(!f.request('preview',{target:t,object_id:10,parameter_tag:1,after:-13,value_kind:'plain',unit:'dB',max_delta:1}).ok);
assert(f.request('preview',{target:t,object_id:10,parameter_tag:1,after:.75,value_kind:'normalized',max_delta:.1}).ok);
console.log('Driver contract passed: real API-shaped mock, identity, scope, current value, epoch, replay, physical conversion, plugin catalog/assignment and API 1.2 fallback.');

}
