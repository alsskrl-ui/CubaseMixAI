"""Master-chain setup checklist derived from actual calibrated controls."""
from .control import load_mapping


def master_chain(mapping_path: str, target: str = 'master') -> dict:
    mapping, digest = load_mapping(mapping_path)
    definitions = [
        ('EQ', [f'{target}.eq.{band}.gain' for band in ('sub','bass','low_mid','mid','presence','air')]),
        ('Compressor', [f'{target}.compressor.{p}' for p in ('threshold','ratio','attack','release')]),
        ('Limiter', [f'{target}.limiter.ceiling']),
    ]
    stages = []
    for order, (name, controls) in enumerate(definitions, 1):
        stages.append({'order': order, 'stage': name,
                       'mapped': {k: mapping['controls'][k] for k in controls if k in mapping['controls']},
                       'manual_or_unmapped': [k for k in controls if k not in mapping['controls']]})
    return {'mapping_sha256': digest, 'stages': stages,
            'setup': ['On a saved test copy, insert EQ → compressor → true-peak limiter on the master bus',
                      'Map exposed parameters through Track Quick Controls/Generic Remote and measure each one',
                      'Confirm plugin units, bypass, order, oversampling and true-peak mode manually',
                      'Use reference-plan --mode master for pending changes; approve before live MIDI',
                      'Export from the same locators/sample rate and use evaluate/AB listening'],
            'automatic_plugin_instantiation': False,
            'reason': 'Cubase 10.5 Generic Remote controls exposed parameters; it cannot instantiate arbitrary plugins or export WAV'}
