"""Reviewable DSP evidence; no invented model listening or DAW readback."""
def recommend(report: dict) -> dict:
    mix = report["mix"]
    delta = report["mix_minus_reference"]
    findings = []
    peak = mix["true_peak_estimate_dbtp"]
    if peak is not None and peak > -1:
        findings.append({"parameter": "master.output_gain", "suggested_delta_db": round(min(0, -1-peak), 2),
                         "reason": f"Estimated true peak {peak:.2f} dBTP exceeds -1 dBTP working ceiling",
                         "confidence": "medium", "risk": "Reduces loudness; does not replace a limiter or certified peak check"})
    for band, diff in delta["bands_percentage_points"].items():
        if abs(diff) >= 8:
            findings.append({"parameter": f"EQ.{band}", "suggested_delta_db": None,
                             "reason": f"Mix/reference energy share differs by {diff:+.1f} percentage points",
                             "confidence": "low", "risk": "Arrangement and instruments may explain difference; audition before setting EQ"})
    findings.append({"parameter": "compressor", "suggested_delta_db": None,
                     "reason": f"Crest difference: {delta['crest_db']} dB",
                     "confidence": "low", "risk": "Attack/release/ratio cannot be inferred reliably from full-mix statistics"})
    return {"findings": findings, "automatic_changes": [], "requires": "Human selects exact mapped values and confirms current Cubase values locally",
            "ai_listening": "Not run; DSP findings are not CLAP judgments"}
