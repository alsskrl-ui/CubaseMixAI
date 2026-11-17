"""Verified plugin insertion followed by fresh parameter mapping and tuning."""
import math

from .client import RemoteClient
from .operations import _map_object
from .workflow import RemoteWorkflow
from ..workflow import Workflow


def _insertion(proposal_id):
    w = Workflow()
    p = w.get(proposal_id)
    if p['status'] != 'verified' or p['payload'].get('backend') != 'midi_remote' or p['payload'].get('kind') != 'plugin':
        raise ValueError('Insert must be applied and verified before parameters can be configured')
    plan = p['payload']['plan']
    children = p['payload']['receipt']['observed']['children']
    if len(children) != 1:
        raise ValueError('Insertion receipt must identify exactly one plugin')
    return w, plan, children[0]


def _current(host, plan, expected):
    slot = host.request('inspect', {'target': plan['target'], 'object_id': plan['object']['object_id']})
    if slot['object'] != plan['object'] or slot['children'] != [expected]:
        raise ValueError('Inserted plugin or slot changed; inspect and create a new workflow')
    return _map_object(host, plan['target'], expected)


def remote_insert_parameters(insert_proposal_id: str) -> dict:
    """After approved insertion is verified, return its CURRENT parameter tags, units and values.

    Start with remote_find_insert, then locally approve/apply that insertion. This tool
    rejects pending/failed insertions and replaced plugin instances; no writes occur.
    """
    _, plan, expected = _insertion(insert_proposal_id)
    with RemoteClient() as host:
        mapped = _current(host, plan, expected)
    return {'insert_proposal_id': insert_proposal_id, 'target': plan['target'],
            'slot': plan['object'], **mapped,
            'next': 'Use these exact tags/units with remote_configure_insert; parameter edits need a new approval.'}


def remote_configure_insert(insert_proposal_id: str, changes: list[dict], reason: str) -> dict:
    """Propose 1..32 parameter edits only on the instance loaded by a verified insertion.

    changes: [{parameter_tag: int OR name: exact title, after: number,
    value_kind: 'plain'|'normalized', unit: string, max_delta: number}].
    Plain values require exact host units, max_delta <=3; normalized values are 0..1,
    max_delta <=.25. Parameter names must be unique. Never assumes parameter order.
    """
    if not isinstance(changes, list) or not 1 <= len(changes) <= 32:
        raise ValueError('Supply 1..32 parameter changes')
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('A reason is required')
    w, plan, expected = _insertion(insert_proposal_id)
    plans, seen = [], set()
    with RemoteClient() as host:
        mapped = _current(host, plan, expected)
        for change in changes:
            if ('parameter_tag' in change) == ('name' in change):
                raise ValueError('Specify exactly one parameter_tag or exact name')
            matches = [p for p in mapped['parameters'] if
                       (p['tag'] == change['parameter_tag'] if 'parameter_tag' in change else
                        p['title'].casefold() == str(change['name']).strip().casefold())]
            if len(matches) != 1:
                raise ValueError('Parameter is missing or ambiguous; use an exposed unique tag')
            current = matches[0]
            if current['tag'] in seen:
                raise ValueError('Duplicate parameter')
            seen.add(current['tag'])
            kind, after, limit = change['value_kind'], change['after'], change['max_delta']
            if kind not in ('plain', 'normalized'):
                raise ValueError('Use plain or normalized values')
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (after, limit)):
                raise ValueError('Values must be finite')
            if not 0 < limit <= (3 if kind == 'plain' else .25):
                raise ValueError('Step exceeds DirectAccess limit')
            unit = change.get('unit', '')
            field = 'plain' if kind == 'plain' else 'normalized'
            before = current.get(field)
            if type(before) not in (int, float) or not math.isfinite(before):
                raise ValueError('Parameter does not expose the requested value representation')
            if (kind == 'plain' and (not unit or unit != current['unit'])) or (kind == 'normalized' and not 0 <= after <= 1):
                raise ValueError('Invalid unit or normalized range')
            if abs(after-before) > limit:
                raise ValueError('Requested change exceeds max_delta')
            args = dict(target=plan['target'], object_id=expected['object_id'], parameter_tag=current['tag'],
                        after=after, value_kind=kind, unit=unit, max_delta=limit)
            fresh = host.request('preview', args)['plan']
            if (fresh['object'] != expected or fresh['before']['title'] != current['title']
                or fresh['before']['unit'] != current['unit']
                or abs(fresh['before'][field] - before) > 1e-5):
                raise ValueError('Plugin parameter changed during preparation')
            plans.append(fresh)
        _current(host, plan, expected)
    return RemoteWorkflow(w).propose_batch(plans, reason, {'insert_proposal_id': insert_proposal_id,
                                                          'plugin_instance': expected})
