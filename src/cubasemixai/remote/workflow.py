"""Approval-gated DirectAccess changes with host-side compare-and-set and readback."""
import math
import time
from .client import RemoteClient


class RemoteWorkflow:
    def __init__(self,workflow,client_factory=None):
        self.w=workflow
        self.client_factory=client_factory or RemoteClient

    def _store(self,plan,reason,evidence=None):
        if not isinstance(reason,str) or not reason.strip():
            raise ValueError('A reviewable reason is required')
        payload={'backend':'midi_remote','kind':plan['kind'],'plan':plan,'reason':reason,'evidence':evidence,
                 'risk':'Actual Cubase values and identity are read, but audio quality and automation behavior require listening. Approval is single-use.'}
        self.w._check_sources(payload)
        return self.w.store(payload)

    def propose(self,target,object_id,parameter_tag,after,reason,value_kind='normalized',unit='',max_delta=.1,evidence=None):
        if type(after) not in (float,int) or type(max_delta) not in (float,int) or not math.isfinite(after) or not math.isfinite(max_delta):
            raise ValueError('Use finite physical or normalized values')
        args={'target':target,'object_id':object_id,'parameter_tag':parameter_tag,'after':after,
              'value_kind':value_kind,'unit':unit,'max_delta':max_delta}
        with self.client_factory() as host:
            result=host.request('preview',args)
        return self._store(result['plan'],reason,evidence)

    def propose_plugin(self,target,slot_id,plugin_uid,reason):
        with self.client_factory() as host:
            result=host.request('preview_plugin',{'target':target,'object_id':slot_id,'plugin_uid':plugin_uid})
        return self._store(result['plan'],reason)

    def _operation(self,prefix,plan):
        return prefix+('_plugin' if plan['kind']=='plugin' else '')

    def _valid(self,p,required):
        if p['status']!=required or time.time()-p['created']>900:
            raise ValueError('Remote proposal is not in the required state or has expired (15 min)')
        self.w._check_sources(p['payload'])

    def decide(self,ident,approve):
        p=self.w.get(ident)
        if not approve:
            with self.w.connect() as con:
                updated=con.execute("UPDATE proposals SET status='rejected' WHERE id=? AND status='pending'",(ident,)).rowcount
            if not updated:raise ValueError('Proposal is not pending')
            return self.w.get(ident)
        self._valid(p,'pending')
        plan=p['payload']['plan']
        with self.client_factory() as host:
            host.request(self._operation('check',plan),{'plan':plan})
        with self.w.connect() as con:
            updated=con.execute("UPDATE proposals SET status='approved' WHERE id=? AND status='pending'",(ident,)).rowcount
        if not updated:raise ValueError('Proposal state changed')
        return self.w.get(ident)

    def apply(self,ident,dry_run=True):
        p=self.w.get(ident);plan=p['payload']['plan']
        self.w._check_sources(p['payload'])
        if dry_run:
            with self.client_factory() as host:
                fresh=host.request(self._operation('check',plan),{'plan':plan})
            return {'dry_run':True,'sent':False,'mutation_sent':False,'backend':'midi_remote','plan':fresh['plan']}
        self._valid(p,'approved')
        with self.client_factory() as host:
            # This client's global port lock spans check, claim, dispatch and verification.
            host.request(self._operation('check',plan),{'plan':plan})
            with self.w.connect() as con:
                con.execute('BEGIN IMMEDIATE')
                row=con.execute('SELECT status,created FROM proposals WHERE id=?',(ident,)).fetchone()
                if row[0]!='approved' or time.time()-row[1]>900:raise ValueError('Approval already used or expired')
                con.execute("UPDATE proposals SET status='sending' WHERE id=?",(ident,))
            try:
                import json
                (self.w.root/(ident+'.before.json')).write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
                receipt=host.request(self._operation('apply',plan),{'plan':plan})
                observed=None
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    if plan['kind']=='parameter':
                        observed=host.request('read',{'plan':plan})
                        matched=abs(observed['parameter']['normalized']-plan['after_normalized'])<=.00001
                    else:
                        observed=host.request('inspect',{'target':plan['target'],'object_id':plan['object']['object_id']})
                        uid=plan['plugin']['uid'].lower()
                        matched=len(observed['children'])==1 and (observed['children'][0]['unique_name'].lower()==uid or observed['children'][0]['unique_name'].lower().startswith(uid+'-'))
                    if matched:break
                    time.sleep(.05)
                else:raise ValueError('Postcondition not observed; outcome is uncertain, never resend automatically')
                p['payload']['receipt']={'dispatch':receipt,'observed':observed}
                with self.w.connect() as con:
                    con.execute("UPDATE proposals SET status='verified', payload=? WHERE id=?",(json.dumps(p['payload'],ensure_ascii=False,allow_nan=False),ident))
            except Exception as exc:
                with self.w.connect() as con:
                    con.execute("UPDATE proposals SET status='uncertain',error=? WHERE id=?",(str(exc),ident))
                raise
        return {'sent':True,'acknowledged_by_cubase':True,'verification':'fresh_direct_access_read',
                'audio_quality_verified':False,'proposal':self.w.get(ident)}

    def restore(self,ident):
        p=self.w.get(ident)
        if p['status'] not in {'verified','uncertain','sending'}:raise ValueError('Only attempted remote changes can be restored')
        plan=p['payload']['plan']
        if plan['kind']!='parameter':raise ValueError('Plugin removal/replacement is manual; automatic plugin restore is unsupported')
        # Capture the ACTUAL current value for the new proposal, not an assumed prior send.
        return self.propose(plan['target'],plan['object']['object_id'],plan['before']['tag'],plan['before']['normalized'],
                            'Restore parameter snapshot for '+ident,'normalized','',.25)
