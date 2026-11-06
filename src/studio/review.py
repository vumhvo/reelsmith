"""QA for a rendered file: numbers + a contact sheet Claude can look at."""

from __future__ import annotations

from pathlib import Path

from . import analyze, ff


def intended_dark(plan) -> list[tuple[float, float]]:
    """Windows where the EDL itself asks for black/dark frames (fades, dark cards)."""
    win = []
    for c in plan.clips:
        t = (c.clip.get("transition") or {}).get("type")
        if c.transition and t in ("fadeblack", "fade", "dissolve", "fadegrays"):
            win.append((c.start - 0.1, c.start + c.transition + 0.1))
        if c.kind == "color":
            win.append((c.start, c.end))
        f = c.clip.get("fade") or {}
        if f.get("in"):
            win.append((c.start, c.start + f["in"] + 0.1))
        if f.get("out"):
            win.append((c.end - f["out"] - 0.1, c.end))
    o = plan.output
    if o.get("fade_in"):
        win.append((0, o["fade_in"] + 0.1))
    if o.get("fade_out"):
        win.append((plan.duration - o["fade_out"] - 0.1, plan.duration + 1))
    return win


def review(path: Path, sheet_out: Path, *, expected_duration: float | None = None,
           target_lufs: float | None = -14, dark_ok: list[tuple[float, float]] | None = None) -> dict:
    info = ff.probe(path)
    dur = info.get("duration", 0.0)
    rep: dict = {"file": str(path), "duration": dur, "size": f"{info.get('width')}x{info.get('height')}",
                 "fps": info.get("fps")}
    issues: list[str] = []

    if info.get("has_audio"):
        st = analyze.audio_stats(path, noise_db=-45, min_silence=1.0)
        rep.update({"lufs": st["integrated_lufs"], "true_peak": st["true_peak_dbfs"],
                    "silences_over_1s": st["silences"]})
        if target_lufs is not None and st["integrated_lufs"] is not None and abs(st["integrated_lufs"] - target_lufs) > 2:
            issues.append(f"loudness {st['integrated_lufs']} LUFS (target {target_lufs})")
        if st["true_peak_dbfs"] is not None and st["true_peak_dbfs"] > -0.5:
            issues.append(f"true peak {st['true_peak_dbfs']} dBFS: risk of clipping")
        if st["silences"]:
            issues.append(f"{len(st['silences'])} silent stretch(es) > 1s: check they are intended")
    else:
        issues.append("no audio track")

    def intended(b):
        return any(b["start"] >= a - 1e-3 and b["end"] <= e + 1e-3 for a, e in (dark_ok or []))
    black = [b for b in analyze.black_segments(path)
             if not (b["start"] < 0.05 or b["end"] > dur - 0.05) and not intended(b)]
    rep["black_segments"] = black
    if black:
        issues.append(f"{len(black)} black segment(s) mid-video: {black[:3]}")
    if expected_duration and abs(dur - expected_duration) > 0.15:
        issues.append(f"duration {dur:.2f}s but EDL expects {expected_duration:.2f}s")

    n = int(min(24, max(8, dur / 2)))
    portrait = (info.get("height") or 0) > (info.get("width") or 0)
    sheet = analyze.contact_sheet(path, sheet_out, count=n, cols=6 if portrait else 4,
                                  thumb_w=200 if portrait else 320, label=f"review: {path.name}")
    rep["sheet"] = sheet["sheet"]
    rep["issues"] = issues
    return rep
