// Original CubaseMixAI driver. ES5 / Steinberg MIDI Remote API v1.
// API contracts: steinbergmedia/midiremote_api_doc. No Node/network/filesystem APIs in Cubase.
'use strict';
var api = require('midiremote_api_v1');
var driver = api.makeDeviceDriver('CubaseMixAI', 'DirectBridge', 'CubaseMixAI');
var input = driver.mPorts.makeMidiInput('Commands');
var output = driver.mPorts.makeMidiOutput('Feedback');
var detect = driver.makeDetectionUnit().detectPortPair(input, output);
detect.expectInputNameEquals('CubaseMixAI To Cubase');
detect.expectOutputNameEquals('CubaseMixAI From Cubase');
var page = driver.mMapping.makePage('CubaseMixAI DirectAccess');
var bank = page.mHostAccess.mMixConsole.makeMixerBankZone('CubaseMixAI channels');
var da = page.mHostAccess.makeDirectAccess ? page.mHostAccess.makeDirectAccess(bank) : null;
var mapping = null;
var device = null;
var session = '';
var generation = 0;
var chunks = {};
var outgoing = [];
var mutations = {};
var mutationCount = 0;
var prefix = [125, 67, 77, 65, 1];
function fail(message) { throw new Error(message); }
function finite(n) { return typeof n === 'number' && isFinite(n); }
function integer(n) { return finite(n) && Math.floor(n) === n && n >= 0; }
function epoch() { generation++; return String(Date.now()) + '-' + generation + '-' + Math.floor(Math.random()*1000000000); }
function optional(name, args) { try { return typeof da[name] === 'function' ? da[name].apply(da, args) : null; } catch (e) { return null; } }
function refresh() {
    if (!mapping || !da) fail('DIRECT_ACCESS_UNAVAILABLE');
    da.update(mapping);
}
function identity(id) {
    return {object_id:id, unique_id:String(da.getObjectUniqueIDString(mapping,id) || ''),
        unique_name:String(da.getObjectUniqueName(mapping,id) || ''), title:String(da.getObjectTitle(mapping,id) || '')};
}
function sameObject(a,b) {
    return a && b && a.object_id===b.object_id && a.unique_id && a.unique_id===b.unique_id && a.unique_name===b.unique_name && a.title===b.title;
}
function children(id) {
    var out=[], count=da.getNumberOfChildObjects(mapping,id), i;
    if (count>256) fail('OBJECT_CHILD_LIMIT');
    for (i=0;i<count;i++) out.push(identity(da.getChildObjectID(mapping,id,i)));
    return out;
}
function channels() {
    refresh();
    var all=children(da.getBaseObjectID(mapping)), i;
    var seen={}, result=[];
    for (i=0;i<all.length;i++) {
        var channel=all[i];
        channel.session=session;
        var previous=seen[channel.object_id];
        if (previous && sameObject(previous,channel)) continue;
        seen[channel.object_id]=channel;
        result.push(channel);
    }
    return result;
}
function target(expected) {
    if (!expected || expected.session!==session || !expected.unique_id) fail('STALE_TARGET_SESSION');
    var all=channels(), matches=[], i;
    for (i=0;i<all.length;i++) if (all[i].unique_id===expected.unique_id) matches.push(all[i]);
    if (matches.length!==1 || !sameObject(matches[0],expected)) fail('TARGET_CHANGED_OR_AMBIGUOUS');
    return matches[0];
}
function scoped(expected,id) {
    var t=target(expected), queue=[t.object_id], seen={}, visits=0, here, list, i;
    if (id===null || id===undefined) id=t.object_id;
    if (!integer(id)) fail('INVALID_OBJECT_ID');
    while (queue.length && visits<1024) {
        here=queue.shift();
        if (seen[here]) continue;
        seen[here]=true; visits++;
        if (here===id) return {target:t, object:identity(here)};
        list=children(here);
        for (i=0;i<list.length;i++) queue.push(list[i].object_id);
    }
    fail('OBJECT_OUTSIDE_TARGET_OR_SCAN_LIMIT');
}
function parameter(id,tag,allowUnreadable) {
    if (!integer(tag)) fail('INVALID_PARAMETER_TAG');
    var count=da.getNumberOfParameters(mapping,id), found=false, i;
    if (count>8192) fail('PARAMETER_SCAN_LIMIT');
    for (i=0;i<count;i++) if (da.getParameterTagByIndex(mapping,id,i)===tag) { found=true; break; }
    if (!found) fail('PARAMETER_NOT_FOUND');
    var value=da.getParameterProcessValue(mapping,id,tag);
    if (!finite(value) || value<0 || value>1) {
        if (!allowUnreadable) fail('INVALID_HOST_VALUE');
        return {tag:tag, title:da.getParameterTitle(mapping,id,tag,128), normalized:null,
            plain:null, unit:optional('getParameterDisplayUnits',[mapping,id,tag]), error:'INVALID_HOST_VALUE'};
    }
    var args=[mapping,id,tag];
    var plain=optional('convertParameterProcessValueToPlain',args.concat([value]));
    return {tag:tag, title:da.getParameterTitle(mapping,id,tag,128), normalized:value,
        display:da.getParameterDisplayValue(mapping,id,tag),
        plain:finite(plain)?plain:null, unit:optional('getParameterDisplayUnits',args),
        value_type:optional('getParameterProcessValueType',args),
        edit_locked:optional('getParameterEditLockState',args), automatable:optional('isParameterAutomatable',args)};
}
function channelFader(args) {
    var channel=target(args.target), id=channel.object_id;
    var count=da.getNumberOfParameters(mapping,id), match=null;
    if (count>8192) fail('PARAMETER_SCAN_LIMIT');
    for (var i=0;i<count;i++) {
        var tag=da.getParameterTagByIndex(mapping,id,i);
        var title=da.getParameterTitle(mapping,id,tag,128);
        if (!/^(volume|channel volume|fader volume)$/i.test(title)) continue;
        if (match!==null) fail('CHANNEL_FADER_AMBIGUOUS');
        match=tag;
    }
    if (match===null) fail('CHANNEL_FADER_NOT_FOUND');
    return {target:channel, parameter:parameter(id,match)};
}
function inspect(args) {
    var loc=scoped(args.target,args.object_id), id=loc.object.object_id;
    var offset=args.parameter_offset===undefined?0:args.parameter_offset;
    if (!integer(offset)) fail('INVALID_OFFSET');
    var count=da.getNumberOfParameters(mapping,id), items=[], i;
    for (i=offset;i<Math.min(count,offset+64);i++) items.push(parameter(id,da.getParameterTagByIndex(mapping,id,i),true));
    return {target:loc.target, object:loc.object, children:children(id), parameters:items,
        parameter_total:count, next_offset:offset+64<count?offset+64:null};
}
function preview(args) {
    var loc=scoped(args.target,args.object_id), before=parameter(loc.object.object_id,args.parameter_tag);
    if (!loc.object.unique_id) fail('OBJECT_IDENTITY_UNAVAILABLE');
    if (before.edit_locked===true) fail('PARAMETER_EDIT_LOCKED');
    if (!finite(args.after) || !finite(args.max_delta) || args.max_delta<=0) fail('INVALID_VALUE');
    var normalized, kind=args.value_kind, plain=null;
    if (kind==='normalized') {
        if (args.after<0 || args.after>1 || args.max_delta>.25 || Math.abs(args.after-before.normalized)>args.max_delta) fail('NORMALIZED_DELTA_OR_RANGE');
        normalized=args.after;
        plain=optional('convertParameterProcessValueToPlain',[mapping,loc.object.object_id,args.parameter_tag,normalized]);
        if (!finite(plain)) plain=null;
    } else if (kind==='plain' || kind==='channel_db') {
        if (kind==='channel_db') {
            if (loc.target.object_id!==loc.object.object_id || /^OutputChannel/.test(loc.target.unique_name) ||
                before.unit!=='dB' || channelFader(args).parameter.tag!==before.tag) fail('CHANNEL_VOLUME_REQUIRED');
        }
        if (args.max_delta>(kind==='channel_db'?24:3) || !finite(before.plain) || !args.unit || args.unit!==before.unit || Math.abs(args.after-before.plain)>args.max_delta) fail('PLAIN_UNIT_OR_DELTA_UNAVAILABLE');
        if (!da.convertParameterPlainToProcessValue || !da.convertParameterProcessValueToPlain) fail('API_1_3_CONVERSION_UNAVAILABLE');
        normalized=da.convertParameterPlainToProcessValue(mapping,loc.object.object_id,args.parameter_tag,args.after);
        if (!finite(normalized) || normalized<0 || normalized>1) fail('PLAIN_OUTSIDE_RANGE');
        plain=da.convertParameterProcessValueToPlain(mapping,loc.object.object_id,args.parameter_tag,normalized);
        if (!finite(plain) || Math.abs(plain-args.after)>Math.max(1,Math.abs(args.after))*.0001) fail('PLAIN_CONVERSION_CLAMPED');
    } else fail('INVALID_VALUE_KIND');
    return {kind:'parameter',target:loc.target,object:loc.object,before:before,
        after_normalized:normalized,after_plain:plain,request:args};
}
function checked(plan) {
    if (!plan || !plan.request) fail('INVALID_PLAN');
    var fresh=preview(plan.request);
    if (!sameObject(plan.object,fresh.object) || plan.before.title!==fresh.before.title || plan.before.unit!==fresh.before.unit ||
        Math.abs(plan.before.normalized-fresh.before.normalized)>.000001 ||
        Math.abs(plan.after_normalized-fresh.after_normalized)>.000001) fail('STALE_PLAN_OR_CURRENT_VALUE');
    return fresh;
}
function readPlan(plan) {
    var loc=scoped(plan.target,plan.object.object_id);
    if (!sameObject(loc.object,plan.object)) fail('PARAMETER_OBJECT_REPLACED');
    var observed=parameter(loc.object.object_id,plan.before.tag);
    if (observed.title!==plan.before.title || observed.unit!==plan.before.unit) fail('PARAMETER_METADATA_CHANGED');
    return {target:loc.target, object:loc.object, parameter:observed};
}
function catalog(args) {
    var loc=scoped(args.target,args.object_id), manager=da.mPluginManager;
    if (!manager || !manager.getPluginCollectionByIndex) fail('PLUGIN_MANAGER_UNAVAILABLE');
    var count=manager.getNumberOfPluginCollections(mapping,loc.object.object_id);
    var index=manager.getIndexOfActivePluginCollection(mapping,loc.object.object_id);
    if (!(index>=0 && index<count)) index=manager.getIndexOfDefaultPluginCollection(mapping,loc.object.object_id);
    if (!(index>=0 && index<count)) fail('PLUGIN_COLLECTION_UNAVAILABLE');
    var col=manager.getPluginCollectionByIndex(mapping,loc.object.object_id,index);
    var entries=col.mEntries || [], offset=args.offset===undefined?0:args.offset, out=[], i,e;
    if (!integer(offset)) fail('INVALID_OFFSET');
    for (i=offset;i<Math.min(entries.length,offset+50);i++) {
        e=entries[i]; out.push({uid:String(e.mPluginUID),name:e.mPluginName,vendor:e.mPluginVendor,version:e.mPluginVersion});
    }
    return {target:loc.target,slot:loc.object,loaded:children(loc.object.object_id),entries:out,
        collection_index:index,total:entries.length,next_offset:offset+50<entries.length?offset+50:null};
}
function pluginPlan(args) {
    var loc=scoped(args.target,args.object_id);
    if (!loc.object.unique_id || children(loc.object.object_id).length) fail('PLUGIN_SLOT_MUST_BE_EMPTY');
    if (typeof args.plugin_uid!=='string' || !/^[0-9a-fA-F]{32}$/.test(args.plugin_uid)) fail('PLUGIN_UID_REQUIRED');
    var pageArgs={target:args.target,object_id:args.object_id,offset:0}, cat, found=null, i;
    do {
        cat=catalog(pageArgs);
        for (i=0;i<cat.entries.length;i++) if (cat.entries[i].uid.toLowerCase()===args.plugin_uid.toLowerCase()) found=cat.entries[i];
        pageArgs.offset=cat.next_offset;
    } while (!found && pageArgs.offset!==null && pageArgs.offset<5000);
    if (!found) fail('PLUGIN_NOT_IN_ACTIVE_CATALOG');
    return {kind:'plugin',target:loc.target,object:loc.object,plugin:found,request:args};
}
var audioCommands={}, queuedAudio=null;
function bindAudioCommand(key,category,name) {
    var trigger=driver.mSurface.makeCustomValueVariable(key);
    page.makeCommandBinding(trigger,category,name);
    audioCommands[key]=trigger;
}
if (driver.mSurface && page.makeCommandBinding) {
    bindAudioCommand('render_selection','Render in Place','Render');
    bindAudioCommand('export_mix','File','Export Audio Mixdown');
    bindAudioCommand('import_audio','File','Import Audio File');
}
function dispatch(op,args) {
    if (op==='hello') {
        var version=api.mDefaults && api.mDefaults.mAppVersion;
        return {driver:'CubaseMixAI/1',host_version:version&&version.getVersionString?version.getVersionString():'unknown',
            capabilities:{direct_access:!!da,physical_conversion:!!(da&&da.convertParameterPlainToProcessValue),
            plugin_manager:!!(da&&da.mPluginManager&&da.mPluginManager.trySetSlotPlugin)}};
    }
    if (op==='audio_command') {
        if (!Object.prototype.hasOwnProperty.call(audioCommands,args.action)) fail('AUDIO_COMMAND_UNAVAILABLE');
        if (queuedAudio) fail('AUDIO_COMMAND_BUSY');
        queuedAudio=audioCommands[args.action];
        return {action:args.action,status:'queued_in_cubase'};
    }
    if (op==='tracks') return {tracks:channels()};
    if (op==='channel_fader') return channelFader(args);
    if (op==='inspect') return inspect(args);
    if (op==='preview') return {plan:preview(args)};
    if (op==='check') return {plan:checked(args.plan)};
    if (op==='read') return readPlan(args.plan);
    if (op==='plugins') return catalog(args);
    if (op==='preview_plugin') return {plan:pluginPlan(args)};
    if (op==='check_plugin') {
        var ready=pluginPlan(args.plan.request);
        if (!sameObject(ready.object,args.plan.object) || ready.plugin.uid!==args.plan.plugin.uid) fail('PLUGIN_SLOT_CHANGED');
        return {plan:ready};
    }
    if (op==='apply') {
        var fresh=checked(args.plan),id=fresh.object.object_id,tag=fresh.before.tag;
        if (da.setParameterEditLockState) da.setParameterEditLockState(mapping,id,tag,true);
        try { da.setParameterProcessValue(mapping,id,tag,fresh.after_normalized); }
        finally { if (da.setParameterEditLockState) da.setParameterEditLockState(mapping,id,tag,false); }
        return {mutation_sent:true, observed:readPlan(fresh)};
    }
    if (op==='apply_plugin') {
        var plugin=dispatch('check_plugin',args).plan;
        var accepted=da.mPluginManager.trySetSlotPlugin(mapping,plugin.object.object_id,plugin.plugin.uid,false);
        return {mutation_sent:true,accepted:!!accepted};
    }
    fail('UNKNOWN_OPERATION');
}
function ascii(value) {
    return JSON.stringify(value).replace(/[\u007f-\uffff]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);});
}
function numberBytes(n,count) { var b=[],i; for(i=0;i<count;i++) b.push((n>>>(7*i))&127); return b; }
function reply(stream,envelope) {
    var text=ascii(envelope), count=Math.ceil(text.length/180),i,j,frame;
    if (text.length>262144) {
        text=ascii({kind:'response',id:envelope.id,ok:false,error:'RESPONSE_TOO_LARGE'});count=Math.ceil(text.length/180);
    }
    for (i=0;i<count;i++) {
        frame=[240].concat(prefix,numberBytes(stream,3),numberBytes(i,2),numberBytes(count,2));
        for (j=i*180;j<Math.min(text.length,(i+1)*180);j++) frame.push(text.charCodeAt(j));
        frame.push(247);outgoing.push(frame);
    }
}
input.mOnSysex=function(activeDevice,message) {
    var data=Array.prototype.slice.call(message),i,stream,index,total,key,part,now=Date.now(),body='',packet,envelope;
    if (!mapping || !device) return;
    if (data[0]===240) data.shift();
    if (data[data.length-1]===247) data.pop();
    for (i=0;i<5;i++) if (data[i]!==prefix[i]) return;
    if (data.length<12 || data.length>192) return;
    for (i=0;i<data.length;i++) if (!integer(data[i]) || data[i]>127) return;
    stream=data[5]+(data[6]<<7)+(data[7]<<14);index=data[8]+(data[9]<<7);total=data[10]+(data[11]<<7);
    if (!stream || total<1 || total>1457 || index>=total) return;
    for(key in chunks) if(chunks.hasOwnProperty(key) && now-chunks[key].time>30000) delete chunks[key];
    if(!chunks[stream] && Object.keys(chunks).length>=8) return;
    part=chunks[stream] || {time:now,total:total,parts:{},count:0};chunks[stream]=part;
    if (part.total!==total) {delete chunks[stream];return;}
    var piece='';for(i=12;i<data.length;i++)piece+=String.fromCharCode(data[i]);
    if (part.parts[index]!==undefined && part.parts[index]!==piece) {delete chunks[stream];return;}
    if (part.parts[index]===undefined) part.count++;
    part.parts[index]=piece;
    if(part.count!==total)return;
    delete chunks[stream];for(i=0;i<total;i++)body+=part.parts[i];
    if(body.length>262144)return;
    try {
        packet=JSON.parse(body);
        if(!packet || typeof packet.id!=='string' || !/^[a-f0-9]{32}$/.test(packet.id))fail('INVALID_REQUEST');
        if(packet.op!=='hello' && packet.session!==session)fail('STALE_SESSION');
        if(packet.op==='apply' || packet.op==='apply_plugin') {
            if(mutations[packet.id])fail('MUTATION_REQUEST_REPLAY');
            if(mutationCount>=512)fail('SESSION_WRITE_LIMIT_REACTIVATE_DRIVER');
            mutations[packet.id]=true;mutationCount++;
        }
        var result=dispatch(packet.op,packet.args||{});result.session=session;
        envelope={kind:'response',id:packet.id,ok:true,result:result};
    } catch(e) {envelope={kind:'response',id:packet?packet.id:'',ok:false,error:String(e.message||e)};}
    reply(stream,envelope);
};
page.mOnIdle=function(activeDevice) {
    var i;for(i=0;i<16 && outgoing.length;i++)output.sendMidi(activeDevice,outgoing.shift());
    if (!outgoing.length && queuedAudio) {
        var trigger=queuedAudio;
        queuedAudio=null;
        trigger.setProcessValue(activeDevice,1);
        trigger.setProcessValue(activeDevice,0);
    }
};
page.mOnActivate=function(activeDevice,activeMapping) {
    device=activeDevice;mapping=activeMapping;session=epoch();chunks={};outgoing=[];mutations={};mutationCount=0;
    if(da)da.activate(mapping);
};
page.mOnDeactivate=function(activeDevice,activeMapping) {
    if(da)da.deactivate(activeMapping);
    queuedAudio=null;mapping=null;device=null;session=epoch();chunks={};outgoing=[];mutations={};
};
