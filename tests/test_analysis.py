import numpy as np
import pytest
import soundfile as sf
from cubasemixai.analysis import analyze, compare


def test_gain_and_identical_reference(tmp_path):
    sr = 48000
    x = .1 * np.sin(2*np.pi*1000*np.arange(sr*2)/sr)
    a, b = tmp_path/'a.wav', tmp_path/'b.wav'
    sf.write(a, x, sr, subtype='FLOAT')
    sf.write(b, x*.5, sr, subtype='FLOAT')
    report = compare(str(a), str(b))
    assert report['mix']['rms_dbfs'] == pytest.approx(-23.0103, abs=.02)
    assert report['mix_minus_reference']['lufs'] == pytest.approx(6.0206, abs=.02)
    assert report['mix']['bands_percent']['mid'] > 99
    assert report['mix']['true_peak_estimate_dbtp'] >= report['mix']['sample_peak_dbfs']
    assert abs(report['mix_minus_reference']['bands_percentage_points']['mid']) < .001


def test_silence_and_stereo(tmp_path):
    p = tmp_path/'a.wav'
    sf.write(p, np.zeros((48000, 2)), 48000)
    r = analyze(str(p))
    assert r['lufs_i'] is None
    assert r['rms_dbfs'] is None
    x = .1*np.sin(np.arange(48000)*.1)
    sf.write(p, np.column_stack([x, -x]), 48000, subtype='FLOAT')
    assert analyze(str(p))['stereo']['correlation'] == pytest.approx(-1)
    with pytest.raises(ValueError): analyze(str(p), end=2)
    with pytest.raises(ValueError): analyze(str(p), start=float('nan'))
