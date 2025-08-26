# README 

This is tool for local copying of big files, such as NGS sequencing fastq files from, say, an external drive to the local HDD/SSD. 

The tool doesn\`t currently support scp or remote transfers.

The main executive script is the `mirror_tool.py` file with the `run-mirror` being a simple shell wrapper, which currently hardcodes my local `venv` to run the script without explicitly activating the responsible `venv`.

## Deprecated 

The `mirror_w_checksums.sh` is a deprecated bash script, that works very slow. I intent to replace it with the `mirror_tool.py` after some testing.

## What this tool does
	•	make‑manifest: recursively hash all files under SRC into a text manifest ("<hash>  <relative/path>").
	•	copy: rsync SRC → DST (use --dry-run to preview).
	•	verify: recompute hashes at DST and ensure they match the manifest.
	•	all: runs (make‑manifest → copy → verify).

## Optional dependencies
	•	BLAKE3: fastest hashing.
	•	Prefer external b3sum (apt install b3sum) or the Python wheel pip install blake3.
	•	If neither is available, the tool falls back to SHA‑256 automatically.
	•	tqdm (optional) for progress bars; otherwise prints periodic counts.

⸻

### A) Use with a dedicated venv (no “activation” required)
	1.	Create the env once (pick where to keep envs):

```bash
mkdir -p /data1/users/antonz/envs
python3 -m venv /data1/users/antonz/envs/mirror-3.10
/data1/users/antonz/envs/mirror-3.10/bin/python -m pip install --upgrade pip
```

# Optional speed/progress:
# - try to get system b3sum
`sudo apt-get update && sudo apt-get install -y b3sum || true`
# - or install Python wheels
`/data1/users/antonz/envs/mirror-3.10/bin/pip install blake3 tqdm`

2.	Put mirror_tool.py somewhere, e.g.:

`/data1/users/antonz/pipeline/unix_scripts/scripts/mirror_tool.py`

3.	(Optional) Create a tiny wrapper so you never need to “activate”:

```bash
# /data1/users/antonz/pipeline/unix_scripts/run-mirror
#!/usr/bin/env bash
exec /data1/users/antonz/envs/mirror-3.10/bin/python \
  /data1/users/antonz/pipeline/unix_scripts/scripts/mirror_tool.py "$@"
```

`chmod +x /data1/users/antonz/pipeline/unix_scripts/run-mirror`

And add the wrapper to the PATH (see below), to call it by its name from anywhere

4.	Use it (your example paths):

Dry run (copy preview only):

```bash
run-mirror \
  --step copy --dry-run \
  /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing/ \
  /data1/users/antonz/data/DM_summer_2025
```

Full run (manifest → copy → verify):

```bash
run-mirror \
  --step all --prefer-external-b3 --jobs 8 \
  /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing/ \
  /data1/users/antonz/data/DM_summer_2025
```

Just make manifest to stdout, then compress:

```bash
/data1/users/antonz/pipeline/unix_scripts/scripts/run-mirror \
  --step make-manifest --manifest - --jobs 8 \
  /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing \
  | gzip > /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing/BLAKE3SUMS.gz
```

Verify from a compressed manifest:

```bash
zcat /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing/BLAKE3SUMS.gz | \
/data1/users/antonz/pipeline/unix_scripts/scripts/run-mirror \
  --step verify --manifest - --jobs 8 \
  /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing \
  /data1/users/antonz/data/DM_summer_2025
```

Exit codes: 0 = success, 1 = verify mismatch, 2 = usage/IO error.

⸻

### B) Docker image

Create Dockerfile next to mirror_tool.py:

```Dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends rsync b3sum && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir tqdm blake3
WORKDIR /app
COPY mirror_tool.py /app/mirror_tool.py
ENTRYPOINT ["python", "/app/mirror_tool.py"]
```

Build:

`docker build -t mirror-b3 .`

Run (mount your source/dest):

Dry run copy:
```bash
docker run --rm \
  -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src:ro \
  -v /data1/users/antonz/data/DM_summer_2025:/dst \
  mirror-b3 --step copy --dry-run /src /dst
```

Full run (manifest → copy → verify):
```bash
docker run --rm \
  -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src:ro \
  -v /data1/users/antonz/data/DM_summer_2025:/dst \
  mirror-b3 --step all --prefer-external-b3 --jobs 8 /src /dst
```

Make manifest to host file:

```
docker run --rm \
  -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src \
  mirror-b3 --step make-manifest --manifest /src/BLAKE3SUMS /src
```

⸻

### C) “Throw‑away” one‑liner container (no local image kept)

If you don’t want to build an image, you can use python:3.11-slim ad‑hoc (slower first time):


```bash
docker run --rm -it \
  -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src:ro \
  -v /data1/users/antonz/data/DM_summer_2025:/dst \
  python:3.11-slim bash -lc '
    apt-get update && apt-get install -y --no-install-recommends rsync b3sum && \
    pip install --no-cache-dir tqdm blake3 && \
    python - <<PY
from urllib.request import urlopen
import sys, os
code = """REPLACEME"""
print("Please mount mirror_tool.py or bake it into the container.")
PY
  '
```

Realistically, for throw‑away use you should mount the script:

```bash
docker run --rm \
  -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src:ro \
  -v /data1/users/antonz/data/DM_summer_2025:/dst \
  -v /data1/users/antonz/pipeline/unix_scripts/scripts/mirror_tool.py:/app/mirror_tool.py:ro \
  python:3.11-slim bash -lc '
    apt-get update && apt-get install -y --no-install-recommends rsync b3sum && \
    pip install --no-cache-dir tqdm blake3 && \
    python /app/mirror_tool.py --step all --prefer-external-b3 --jobs 8 /src /dst
  '
```

(Using --rm makes the container ephemeral.)

⸻

Notes & tips
	•	Performance: HDDs tend to like --jobs 4..8; NVMe can go to $(nproc).
	•	Algorithm choice:
	•	--algo auto (default): tries external b3sum, then Python blake3, then falls back to sha256.
	•	Force SHA‑256 if you must: --algo sha256.
	•	Manifests: by default saved as BLAKE3SUMS (or SHA256SUMS if you force sha256). Use --manifest - to stream.
	•	Dry run: only affects the copy step (preview with rsync). Manifest and verify are real actions unless you run --step copy --dry-run.

That’s it. This setup stays faithful to the “single‑purpose tools that compose” idea:
	•	pyenv (optional) picks your interpreter,
	•	venv isolates dependencies,
	•	mirror_tool.py orchestrates,
	•	b3sum/rsync do the heavy lifting,
	•	and everything pipes cleanly.


# Options to use the script by its short name without the full path:

⸻

### 1. Put it on your $PATH

If you want to type run-mirror anywhere (like a real command), just make sure the script lives in a directory that’s on your PATH.

Example:
```bash
# move it to a local bin directory
mkdir -p ~/bin
cp /data1/users/antonz/pipeline/unix_scripts/run-mirror ~/bin/

# add ~/bin to PATH if not already there
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Now you can just run:

`run-mirror /mnt/... /data1/...`

This is cleaner than an alias because it behaves like a proper executable.

⸻

2. Use a shell alias

If you want to keep the script where it is, you can alias it:

`echo 'alias run-mirror="/data1/users/antonz/pipeline/unix_scripts/run-mirror"' >> ~/.bash_aliases`

Then reload:

`source ~/.bashrc   # ~/.bash_aliases is sourced by bashrc if it exists`

Now run-mirror calls the full script.

⸻

Which is better?
	•	PATH solution is more “Unix-y”: your script is a real command, can be used in cron, Makefiles, other scripts, etc.
	•	alias in .bash_aliases is quick-and-dirty, but aliases only expand in interactive shells (not in scripts or cron).

⸻

Keep your personal utilities in ~/bin/ or ~/scripts/ and add that directory to PATH.

In my personal case I have added my development library with the script onto the `$PATH`
```
### **Add to** **~/.bashrc** **(Ubuntu default for interactive shells)**

```bash
DIR="/data1/users/antonz/pipeline/unix_scripts/scripts"
# Add only if not present
if ! echo ":$PATH:" | grep -q ":$DIR:"; then
  export PATH="$DIR:$PATH"   # prepend to give your tools priority
fi
```