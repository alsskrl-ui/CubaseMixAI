const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[2],'utf8');
const source=html.slice(html.indexOf("const autoButton="),html.indexOf("token.addEventListener"));
async function scenario(stopAfterApproval=false,fail=false){
 const calls=[],timers=[];let refreshes=0;
 const button={pressed:'false',getAttribute(){return this.pressed},setAttribute(k,v){this.pressed=v}};
 const context={document:{querySelector:()=>button},message:{},show(){},refresh:async()=>{refreshes++},setTimeout:fn=>timers.push(fn)};
 context.api=async(path,body)=>{
   calls.push(path);
   if(path==='/auto/start')return {};
   if(path==='/auto/queue')return [{id:'old',status:'pending'},{id:'approved',status:'approved'}];
   if(path==='/decision/old' && stopAfterApproval)context.stopAuto();
   if(path.startsWith('/apply')&&fail)throw Error('connection lost');
   return {};
 };
 vm.createContext(context);vm.runInContext(source,context);
 await button.onclick();
 for(let i=0;i<20;i++)await Promise.resolve();
 if(stopAfterApproval){assert(!calls.some(x=>x.startsWith('/apply')));return;}
 if(fail){assert.equal(button.pressed,'false');assert.equal(timers.length,0);return;}
 assert(calls.includes('/decision/old'));assert(calls.includes('/apply/old'));assert(calls.includes('/apply/approved'));
 assert(!calls.includes('/decision/approved'));assert(refreshes>0);assert.equal(timers.length,1);
 await timers.shift()();
 assert.equal(calls.filter(x=>x==='/apply/old').length,1);
}
(async()=>{await scenario();await scenario(true);await scenario(false,true);console.log('Auto poll contract passed')})().catch(e=>{console.error(e);process.exitCode=1});
