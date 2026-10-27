"""TEST DOUBLE for web/render/render.mjs. Same CLI and stdout protocol; never used in production.

FAKE_MODE: ok | badres | noaudio | shortdur | fail | errorjson | hang | silentdone | nofile
FAKE_PIDS: file to which `hang` writes its own pid and its child's pid.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

args = sys.argv[1:]
opts = {args[i]: args[i + 1] for i in range(0, len(args), 2)}
props = json.loads(Path(opts["--props"]).read_text(encoding="utf-8"))
mode = os.environ.get("FAKE_MODE", "ok")
seconds = props["timeline"]["duration_frames"] / props["timeline"]["fps"]
Path(opts["--out"]).with_name("fake.args.json").write_text(json.dumps(sys.argv[1:]), encoding="utf-8")


def say(**kw):
    print(json.dumps(kw), flush=True)


if mode == "hang":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    Path(os.environ["FAKE_PIDS"]).write_text(f"{os.getpid()} {child.pid}", encoding="utf-8")
    say(progress=0.1)
    time.sleep(600)
if mode == "fail":
    print("not json log line", flush=True)
    sys.stderr.write("chrome exploded\n")
    sys.exit(1)
if mode == "errorjson":
    say(error="composition Lesson not found")
    sys.exit(1)
if mode == "silentdone":
    sys.exit(0)

size = "640x360" if mode == "badres" else "1280x720"
dur = seconds + (1.0 if mode == "shortdur" else 0.0)
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c=blue:s={size}:r=30:d={dur}"]
if mode != "noaudio":
    cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:d={dur}", "-c:a", "aac", "-b:a", "128k"]
cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30", "-preset", "ultrafast", "-t", str(dur), opts["--out"]]
say(progress=0.25)
say(progress=0.5)
if mode != "nofile":
    subprocess.run(cmd, check=True)
say(progress=1.0)
say(done=True, out=opts["--out"], ms=5)
