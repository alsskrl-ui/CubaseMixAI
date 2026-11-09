"""Local CLAP audio/text embeddings with explicit prompt and window uncertainty."""
from pathlib import Path
from math import gcd
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from .analysis import fingerprint

PROMPTS = {
    'brightness': ['The music has a dark and muffled timbre.', 'The music has a bright and clear timbre.'],
    'punch': ['The music has soft and weak drum transients.', 'The music has punchy and impactful drum transients.'],
    'space': ['The music sounds dry and close with little reverberation.', 'The music sounds spacious with audible reverberation.'],
}


def _unit(x):
    x = np.asarray(x, dtype=float)
    norm = np.linalg.norm(x, axis=-1, keepdims=True)
    if not np.isfinite(x).all() or np.any(norm <= 0):
        raise ValueError('Model returned invalid embeddings')
    return x / norm


def _windows(path: str):
    info = sf.info(path)
    if info.format not in {'WAV', 'WAVEX', 'RF64'} or info.channels not in (1, 2):
        raise ValueError('CLAP requires mono/stereo WAV')
    if not .4 <= info.duration <= 30:
        raise ValueError('Export matching 0.4–30 second clips for CLAP')
    x, sr = sf.read(path, always_2d=True, dtype='float32')
    if not np.isfinite(x).all() or np.max(np.abs(x)) == 0:
        raise ValueError('Need finite non-silent audio')
    # Energy-preserving stereo downmix avoids cancelling opposite-phase channels.
    mono = x[:, np.argmax(np.mean(x*x, axis=0))] if x.shape[1] == 2 else x[:, 0]
    factor = gcd(sr, 48000)
    mono = resample_poly(mono, 48000//factor, sr//factor)
    # Same deterministic crop policy for mix and reference. No random model truncation.
    length = min(len(mono), 480000)
    starts = sorted(set([0, (len(mono)-length)//2, len(mono)-length]))
    result = []
    for start in starts:
        clip = mono[start:start+length].copy()
        rms = float(np.sqrt(np.mean(clip**2)))
        if rms <= 0:
            continue
        gain = min(.1/rms, .95/max(float(np.max(np.abs(clip))), 1e-12))
        result.append((clip*gain).astype('float32'))
    if not result:
        raise ValueError('No non-silent CLAP windows')
    return result


def score_embeddings(mix_embeddings, reference_embeddings, text_embeddings) -> dict:
    """Pure scoring step: testable without downloading model weights."""
    a, b, texts = _unit(mix_embeddings), _unit(reference_embeddings), _unit(text_embeddings)
    if a.ndim != 2 or b.ndim != 2 or texts.shape != (6, a.shape[1]) or b.shape[1] != a.shape[1]:
        raise ValueError('Unexpected embedding dimensions')
    cosine = float(np.dot(_unit(a.mean(axis=0)), _unit(b.mean(axis=0))))
    dimensions = {}
    for i, name in enumerate(PROMPTS):
        direction = texts[2*i+1]-texts[2*i]
        am, bm = a @ direction, b @ direction
        delta = float(am.mean()-bm.mean())
        spread = float(np.sqrt(am.var()+bm.var()))
        dimensions[name] = {'mix_prompt_margin': float(am.mean()), 'reference_prompt_margin': float(bm.mean()),
                            'mix_minus_reference': delta, 'window_spread': spread,
                            'confidence': 'low' if len(a) < 2 or len(b) < 2 or abs(delta) <= spread+.02 else 'medium',
                            'interpretation': 'Prompt affinity, not a perceptual quality rating'}
    return {'cosine_similarity': cosine, 'dimensions': dimensions,
            'window_counts': {'mix': len(a), 'reference': len(b)},
            'confidence': 'uncalibrated', 'prompts': PROMPTS,
            'limitations': ['Prompt scores are not probabilities or quality ratings',
                           'Training bias, arrangement and window choice affect results',
                           'Human loudness-matched listening is required', 'CLAP uses the louder channel; use DSP metrics for stereo width']}


def clap_compare(mix: str, reference: str, model_dir: str) -> dict:
    """Use a prepared local transformers CLAP directory. Never download on inference."""
    if not Path(model_dir).is_dir():
        raise ValueError('Run setup-ai with a local output directory first')
    from transformers import ClapModel, ClapProcessor
    import torch
    source_hashes = {'mix_sha256': fingerprint(mix), 'reference_sha256': fingerprint(reference)}
    model_hash = fingerprint(str(Path(model_dir)/'model.safetensors'))
    a, b = _windows(mix), _windows(reference)
    processor = ClapProcessor.from_pretrained(model_dir, local_files_only=True)
    model = ClapModel.from_pretrained(model_dir, local_files_only=True, use_safetensors=True).eval().to('cpu')
    def audio_features(windows):
        result = []
        for clip in windows:
            inputs = processor(audio=clip, sampling_rate=48000, return_tensors='pt')
            with torch.inference_mode():
                embedding = model.get_audio_features(**inputs)
            if hasattr(embedding, 'pooler_output'):
                embedding = embedding.pooler_output
            result.append(embedding.cpu().numpy()[0])
        return np.asarray(result)
    prompts = [p for pair in PROMPTS.values() for p in pair]
    text = processor(text=prompts, return_tensors='pt', padding=True)
    with torch.inference_mode():
        features = model.get_text_features(**text)
    if hasattr(features, 'pooler_output'):
        features = features.pooler_output
    result = score_embeddings(audio_features(a), audio_features(b), features.cpu().numpy())
    if source_hashes != {'mix_sha256': fingerprint(mix), 'reference_sha256': fingerprint(reference)} or model_hash != fingerprint(str(Path(model_dir)/'model.safetensors')):
        raise ValueError('Audio or model changed during CLAP inference')
    result.update(model='LAION CLAP / transformers', model_dir=str(Path(model_dir).resolve()),
                  model_sha256=model_hash, inputs=source_hashes)
    return result


def setup_ai(output: str) -> dict:
    """Fetch an official pinned revision, load tensors only, save local safetensors."""
    from huggingface_hub import HfApi, snapshot_download
    from transformers import ClapModel
    import json
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('Use a new empty model directory')
    revision = HfApi().model_info('laion/clap-htsat-unfused').sha
    snapshot_download('laion/clap-htsat-unfused', revision=revision, local_dir=output,
                      allow_patterns=['*.json', 'merges.txt', 'vocab.json', 'pytorch_model.bin'])
    # Official repo currently provides PyTorch weights. torch>=2.6 and
    # weights_only=True avoid arbitrary-object pickle loading; inference uses safetensors.
    model = ClapModel.from_pretrained(output, local_files_only=True, use_safetensors=False, weights_only=True)
    model.save_pretrained(output, safe_serialization=True)
    (out/'pytorch_model.bin').unlink()
    manifest = {'source': 'laion/clap-htsat-unfused', 'revision': revision,
                'sha256': fingerprint(str(out/'model.safetensors'))}
    (out/'cubasemixai-model.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'model_dir': str(out), **manifest}
