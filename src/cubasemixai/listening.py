"""Optional local CLAP similarity. Similarity is not a mixing-quality score."""
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd


def clap_compare(mix: str, reference: str, checkpoint: str) -> dict:
    if not Path(checkpoint).is_file():
        raise ValueError("Provide a trusted local CLAP checkpoint; no automatic downloads")
    import laion_clap
    model = laion_clap.CLAP_Module(enable_fusion=False, device="cpu")
    model.load_ckpt(ckpt=checkpoint)
    audio = []
    for path in (mix, reference):
        info = sf.info(path)
        if info.duration > 30:
            raise ValueError("Export matching clips of at most 30 seconds for CLAP")
        x, sr = sf.read(path, always_2d=True, dtype="float32")
        x = x.mean(axis=1)
        if not len(x) or not np.isfinite(x).all() or np.max(np.abs(x)) == 0:
            raise ValueError("Need finite non-silent audio")
        factor = gcd(sr, 48000)
        audio.append(resample_poly(x, 48000//factor, sr//factor))
    # Individual calls allow unequal clip durations.
    embeddings = [model.get_audio_embedding_from_data(x=x[None, :], use_tensor=False)[0] for x in audio]
    a, b = embeddings
    cosine = float(np.dot(a, b)/(np.linalg.norm(a)*np.linalg.norm(b)))
    return {"model": "LAION CLAP", "cosine_similarity": cosine,
            "limitations": ["Semantic similarity is not mix quality", "Does not establish punch, space, or EQ correctness", "Short clips and training-domain bias affect results"],
            "checkpoint": str(Path(checkpoint).resolve())}
