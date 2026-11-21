import json
import sys
import time
import wave

import numpy as np
import onnx_asr

path = sys.argv[1]
with wave.open(path) as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
total = len(audio) / 16000

model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", quantization="int8")
model = model.with_vad(onnx_asr.load_vad("silero"), max_speech_duration_s=25)

t, last = time.time(), 0.0
for seg in model.recognize(audio, sample_rate=16000):
    print(json.dumps({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()},
                     ensure_ascii=False), flush=True)
    if seg.end - last >= 300:
        last = seg.end
        print(f"  {seg.end / 60:.0f}/{total / 60:.0f} min ({seg.end / (time.time() - t):.0f}× real time)",
              file=sys.stderr, flush=True)
