"""Read-only inspection and pending proposals for the modern backend."""
from .client import RemoteClient


def remote_status() -> dict:
    """Read actual driver identity, host version and feature flags."""
    with RemoteClient() as host:
        return host.hello


def remote_tracks() -> dict:
    """List mixer channels with session-scoped unique identities, not bank addresses."""
    with RemoteClient() as host:
        return host.request('tracks',{})


def remote_inspect(target: dict, object_id: int | None = None, parameter_offset: int = 0) -> dict:
    """Inspect a track or descendant object; enumerate physical units/parameters/children."""
    with RemoteClient() as host:
        return host.request('inspect',{'target':target,'object_id':object_id,'parameter_offset':parameter_offset})


def remote_plugins(target: dict, slot_id: int, offset: int = 0) -> dict:
    """Read the installed plugin catalog for a real insert slot (API 1.3 required)."""
    with RemoteClient() as host:
        return host.request('plugins',{'target':target,'object_id':slot_id,'offset':offset})


def remote_propose(target: dict, object_id: int, parameter_tag: int, after: float,
                   reason: str, value_kind: str = 'normalized', unit: str = '', max_delta: float = .1) -> dict:
    """Read current host value and prepare a pending change. No mutation or approval."""
    from .workflow import RemoteWorkflow
    from ..workflow import Workflow
    return RemoteWorkflow(Workflow()).propose(target,object_id,parameter_tag,after,reason,value_kind,unit,max_delta)


def remote_propose_plugin(target: dict, slot_id: int, plugin_uid: str, reason: str) -> dict:
    """Prepare an empty-slot plugin assignment; requires local UI approval; no replacement."""
    from .workflow import RemoteWorkflow
    from ..workflow import Workflow
    return RemoteWorkflow(Workflow()).propose_plugin(target,slot_id,plugin_uid,reason)


def _read_db_fader(host, target: dict, object_id: int, parameter_tag: int) -> dict:
    offset=0
    while offset is not None:
        inspected=host.request('inspect',{'target':target,'object_id':object_id,'parameter_offset':offset})
        found=next((p for p in inspected['parameters'] if p['tag']==parameter_tag),None)
        if found is not None: break
        offset=inspected['next_offset']
    if found is None:
        raise ValueError('Fader parameter tag was not found on the supplied Cubase object')
    if not isinstance(found.get('unit'),str) or found['unit'].strip().lower()!='db' or not isinstance(found.get('plain'),(int,float)):
        raise ValueError('Fader must expose a readable dB plain value')
    if not any(label in str(found.get('title','')).lower() for label in ('volume','fader','level')):
        raise ValueError('Selected parameter title is not identified as a volume/fader/level control')
    return found


def remote_propose_reference_volumes(track_pairs: list[dict], max_track_step_db: float = 1.0,
                                     reason: str = 'Conservative stem-matched fader proposal',
                                     state_dir: str | None = None) -> dict:
    """Compare explicitly paired stems and create one approval-gated fader batch.

    Each item contains target, object_id, parameter_tag, mix_wav, and
    reference_wav. No track or stem matching is guessed. Master peak targeting
    is a separate post-render step.
    """
    import math
    from ..analysis import compare
    from ..workflow import Workflow
    from .workflow import RemoteWorkflow

    if not isinstance(track_pairs,list) or not 1<=len(track_pairs)<=32:
        raise ValueError('Provide 1–32 explicitly matched track/stem pairs')
    if type(max_track_step_db) not in (int,float) or not math.isfinite(max_track_step_db) or not 0<max_track_step_db<=3:
        raise ValueError('Per-track fader step must be greater than 0 and at most 3 dB')
    entries=[];sources={};seen=set();summaries=[]
    for item in track_pairs:
        for key in ('target','object_id','parameter_tag','mix_wav','reference_wav'):
            if key not in item: raise ValueError('Each pair needs target, object_id, parameter_tag, mix_wav and reference_wav')
        target=item['target']
        if not isinstance(target,dict) or not target.get('session') or not target.get('unique_id'):
            raise ValueError('Use the complete session-scoped target returned by remote_tracks')
        if item['object_id']!=target.get('object_id'):
            raise ValueError('Track Volume must be read from the mixer-channel object itself')
        ident=(target['unique_id'],item['object_id'],item['parameter_tag'])
        if ident in seen: raise ValueError('Duplicate Cubase track/volume parameter in batch')
        seen.add(ident)
        report=compare(item['mix_wav'],item['reference_wav'])
        mix_lufs,ref_lufs=report['mix']['lufs_i'],report['reference']['lufs_i']
        if mix_lufs is None or ref_lufs is None: raise ValueError('Cannot match silent or invalid stem pair')
        delta=ref_lufs-mix_lufs
        step=max(-max_track_step_db,min(max_track_step_db,delta))
        entries.append({'target':target,'object_id':item['object_id'],'parameter_tag':item['parameter_tag'],
                        'step_db':step,'delta_db':delta,'report':report})
        for key in ('mix','reference'):
            audio=report[key];sources[audio['path']]=audio['sha256']

    plans=[]
    with RemoteClient() as host:
        for item in entries:
            found=_read_db_fader(host,item['target'],item['object_id'],item['parameter_tag'])
            current=float(found['plain']);step=item['step_db']
            summary={'track':found['title'],'current_fader_db':current,'mix_stem_lufs':item['report']['mix']['lufs_i'],
                     'reference_stem_lufs':item['report']['reference']['lufs_i'],'measured_difference_db':item['delta_db'],
                     'proposed_step_db':step,'remaining_lufs_difference_db':item['delta_db']-step}
            if abs(step)<.01:
                summary['status']='already_matched';summaries.append(summary);continue
            args={'target':item['target'],'object_id':item['object_id'],'parameter_tag':item['parameter_tag'],
                  'after':current+step,'value_kind':'plain','unit':'dB','max_delta':float(max_track_step_db)}
            plan=host.request('preview',args)['plan']
            if abs(plan['before']['plain']-current)>.001:
                raise ValueError('Cubase fader changed while preparing this batch; read all values again')
            plans.append(plan);summary['proposed_fader_db']=current+step;summaries.append(summary)
    if not plans:
        return {'proposal':None,'tracks':summaries,'already_at_targets':True,
                'requires':'All paired faders already match within 0.01 dB; no change was proposed.'}
    evidence={'source_files':[{'path':path,'sha256':digest} for path,digest in sorted(sources.items())],
              'method':'Pairwise integrated-LUFS differences propose bounded fader steps. This is not stem separation or a guaranteed mix match.',
              'summary':summaries}
    proposal=RemoteWorkflow(Workflow(state_dir)).propose_batch(
        plans,reason,evidence)
    return {'proposal':proposal,'tracks':summaries,
            'requires':'One local approval. Faders are written sequentially and individually read back; a connection failure can leave a partial batch marked uncertain. Re-render stems before a follow-up match.'}


def remote_propose_master_peak(target: dict, object_id: int, parameter_tag: int,
                               master_wav: str, target_peak_db: float = -6.0,
                               peak_metric: str = 'sample_peak_dbfs', max_step_db: float = 3.0,
                               state_dir: str | None = None) -> dict:
    """Propose a master-fader step from an exported master WAV peak measurement."""
    import math
    from ..analysis import analyze
    from ..workflow import Workflow
    from .workflow import RemoteWorkflow

    if peak_metric not in {'sample_peak_dbfs','true_peak_estimate_dbtp'}:
        raise ValueError('Use sample_peak_dbfs or true_peak_estimate_dbtp')
    if type(target_peak_db) not in (int,float) or not math.isfinite(target_peak_db):
        raise ValueError('Target peak must be a finite dB value for the selected metric')
    if type(max_step_db) not in (int,float) or not math.isfinite(max_step_db) or not 0<max_step_db<=3:
        raise ValueError('Master fader step must be greater than 0 and at most 3 dB')
    if not isinstance(target,dict) or not target.get('session') or not target.get('unique_id'):
        raise ValueError('Use the complete master target returned by remote_tracks')
    if object_id!=target.get('object_id'):
        raise ValueError('Master Volume must be read from the mixer-channel object itself')
    report=analyze(master_wav)
    measured=report.get(peak_metric)
    if measured is None: raise ValueError('Master WAV peak could not be measured')
    requested=float(target_peak_db)-float(measured)
    step=max(-max_step_db,min(max_step_db,requested))
    summary={'master_wav':report['path'],'peak_metric':peak_metric,'measured_peak_db':measured,
             'target_peak_db':float(target_peak_db),'requested_fader_step_db':requested,
             'proposed_fader_step_db':step,'remaining_peak_difference_db':requested-step}
    if abs(requested)<.05:
        return {'proposal':None,'master':summary,'already_at_target':True,
                'requires':'Rendered master peak is already within 0.05 dB of target.'}
    with RemoteClient() as host:
        found=_read_db_fader(host,target,object_id,parameter_tag)
        current=float(found['plain']);after=current+step
        args={'target':target,'object_id':object_id,'parameter_tag':parameter_tag,'after':after,
              'value_kind':'plain','unit':'dB','max_delta':float(max_step_db)}
        plan=host.request('preview',args)['plan']
        if abs(plan['before']['plain']-current)>.001:
            raise ValueError('Master fader changed while preparing this proposal; inspect it again')
    evidence={'source_files':[{'path':report['path'],'sha256':report['sha256']}],
              'master_peak_analysis':report,'target_peak_db':float(target_peak_db),
              'method':'One-to-one peak-to-fader correction estimate; export and measure again after applying.'}
    proposal=RemoteWorkflow(Workflow(state_dir))._store(
        plan,f"Move master output peak toward {target_peak_db:.2f} using {peak_metric}",evidence)
    summary.update({'master_fader_title':found['title'],'current_master_fader_db':current,
                    'proposed_master_fader_db':after})
    return {'proposal':proposal,'master':summary,
            'requires':'Approve locally, apply once, re-export the master WAV and measure again. Downstream compression, limiting, automation, or routing can change the result; this is not a guaranteed ceiling.'}
