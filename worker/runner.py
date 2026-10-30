"""Redis-backed demo worker. Executes each job in a disposable locked-down Docker container."""
import json, os, pathlib, shutil, subprocess, tempfile, time
from redis import Redis
from app.db import connect

redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
IMAGES = {"python": "python:3.12-alpine", "javascript": "node:22-alpine", "java": "eclipse-temurin:21-jdk", "cpp": "gcc:14"}
FILES = {"python": "main.py", "javascript": "main.js", "java": "Main.java", "cpp": "main.cpp"}
COMMANDS = {
    "python": ["python", "/src/main.py"],
    "javascript": ["node", "/src/main.js"],
    "java": ["sh", "-lc", "cd /tmp && javac /src/Main.java -d /tmp && java -cp /tmp Main"],
    "cpp": ["sh", "-lc", "g++ -O2 /src/main.cpp -o /tmp/main && /tmp/main"],
}

def update(sid, status, result=None):
    with connect() as conn:
        conn.execute("UPDATE submissions SET status=%s,result=%s::jsonb,finished_at=CASE WHEN %s IN ('done','error') THEN now() ELSE NULL END WHERE id=%s",
          (status, json.dumps(result) if result is not None else None, status, sid))

def run(sid):
    with connect() as conn:
        job = conn.execute("SELECT * FROM submissions WHERE id=%s", (sid,)).fetchone()
    if not job: return
    lang = job["language"]
    update(sid, "running")
    work = pathlib.Path(tempfile.mkdtemp(prefix="judge-"))
    volume = f"judge-job-{sid.replace('-', '')}"
    stage = f"judge-stage-{sid.replace('-', '')}"
    try:
        (work / FILES[lang]).write_text(job["source"], encoding="utf-8")
        # A per-job Docker volume avoids host-path translation problems on Windows
        # and prevents one submission from seeing another submission's source.
        subprocess.run(["docker", "volume", "create", volume], check=True, capture_output=True, text=True)
        subprocess.run(["docker", "run", "-d", "--network=none", "--name", stage, "--mount", f"type=volume,src={volume},dst=/src", IMAGES[lang], "sh", "-c", "sleep 60"], check=True, capture_output=True, text=True)
        subprocess.run(["docker", "cp", str(work / FILES[lang]), f"{stage}:/src/{FILES[lang]}"], check=True, capture_output=True, text=True)
        subprocess.run(["docker", "rm", "-f", stage], check=False, capture_output=True, text=True)
        args = ["docker", "run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64", "--memory=256m", "--cpus=0.5", "--user=65534:65534", "--tmpfs", "/tmp:rw,exec,nosuid,size=64m", "--mount", f"type=volume,src={volume},dst=/src,readonly", "--workdir=/src", "--interactive", "--runtime", "runc", IMAGES[lang], *COMMANDS[lang]]
        started = time.monotonic()
        try:
            proc = subprocess.run(args, input=job["stdin"], text=True, capture_output=True, timeout=5)
            elapsed = round((time.monotonic()-started)*1000)
            stdout, stderr, code = proc.stdout[:12000], proc.stderr[:4000], proc.returncode
            verdict = "accepted" if code == 0 and stdout.strip() == job["expected"].strip() else ("wrong_answer" if code == 0 else "runtime_error")
        except subprocess.TimeoutExpired as e:
            timeout_out = e.stdout or ""
            if isinstance(timeout_out, bytes): timeout_out = timeout_out.decode(errors="replace")
            stdout, stderr, code, elapsed, verdict = timeout_out[:12000], "time limit exceeded", -1, 5000, "time_limit"
        result = {"verdict": verdict, "exit_code": code, "stdout": stdout, "stderr": stderr, "runtime_ms": elapsed}
        update(sid, "done", result)
    except Exception as e:
        update(sid, "error", {"verdict":"internal_error", "stderr":str(e)[:1000]})
    finally:
        subprocess.run(["docker", "rm", "-f", stage], check=False, capture_output=True, text=True)
        subprocess.run(["docker", "volume", "rm", "-f", volume], check=False, capture_output=True, text=True)
        shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    print("judge worker ready; waiting for submissions")
    while True:
        item = redis.blpop("judge:queue", timeout=5)
        if item:
            run(item[1])
