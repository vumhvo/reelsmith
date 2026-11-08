"""SAM 2 video tracking worker. Runs in its own environment through `uvx` (torch + sam2), never imported.

usage: python -I roto_worker.py <config.json>

config: {"frames": dir of 00000.jpg..., "out": dir, "model": "facebook/sam2.1-hiera-small",
         "prompts": [{"id": 1, "frame": 0, "pos": [[x, y]], "neg": [[x, y]], "box": [x0, y0, x1, y1]}]}
Coordinates are pixels of the extracted frames. Writes out/obj<id>/00000.png... (white = object) for
every frame, then prints one JSON line {"frames": N, "objects": [...], "device": "mps"}.
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from sam2.sam2_video_predictor import SAM2VideoPredictor  # noqa: E402


def main() -> None:
    cfg = json.loads(Path(sys.argv[1]).read_text())
    frames, out = Path(cfg["frames"]), Path(cfg["out"])
    n_frames = len(list(frames.glob("*.jpg")))
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    print(f"loading {cfg['model']} on {device} ({n_frames} frames)...", file=sys.stderr, flush=True)
    pred = SAM2VideoPredictor.from_pretrained(cfg["model"], device=device)

    ids = sorted({int(p["id"]) for p in cfg["prompts"]})
    for i in ids:
        (out / f"obj{i}").mkdir(parents=True, exist_ok=True)
    written: dict[int, set] = {i: set() for i in ids}

    def save(idx, obj_ids, logits):
        for j, oid in enumerate(obj_ids):
            m = (logits[j, 0] > 0).cpu().numpy().astype(np.uint8) * 255
            Image.fromarray(m).save(out / f"obj{oid}" / f"{idx:05d}.png")
            written[int(oid)].add(int(idx))

    with torch.inference_mode():
        state = pred.init_state(video_path=str(frames), offload_video_to_cpu=True)
        for p in cfg["prompts"]:
            pts = [*p.get("pos", []), *p.get("neg", [])]
            kw = {}
            if pts:
                kw["points"] = np.array(pts, dtype=np.float32)
                kw["labels"] = np.array([1] * len(p.get("pos", [])) + [0] * len(p.get("neg", [])), dtype=np.int32)
            if p.get("box"):
                kw["box"] = np.array(p["box"], dtype=np.float32)
            pred.add_new_points_or_box(state, frame_idx=int(p["frame"]), obj_id=int(p["id"]), **kw)
        first = min(int(p["frame"]) for p in cfg["prompts"])
        for idx, obj_ids, logits in pred.propagate_in_video(state):
            save(idx, obj_ids, logits)
        if first > 0:  # prompts after the first frame: also track backwards to frame 0
            for idx, obj_ids, logits in pred.propagate_in_video(state, reverse=True):
                save(idx, obj_ids, logits)

    # frames SAM 2 never produced (should not happen) become empty masks so the sequence has no holes
    size = Image.open(next(iter(sorted(frames.glob("*.jpg"))))).size
    for oid, got in written.items():
        for idx in range(n_frames):
            if idx not in got:
                Image.new("L", size, 0).save(out / f"obj{oid}" / f"{idx:05d}.png")
    print(json.dumps({"frames": n_frames, "objects": ids, "device": device}))


if __name__ == "__main__":
    main()
