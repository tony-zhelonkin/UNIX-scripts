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

Let me examine the command-line arguments that the `mirror_tool.py` accepts to give you a comprehensive overview of all available options.
Read file: /data1/users/antonz/pipeline/unix_scripts/scripts/mirror_tool.py
Now let me check if there are any environment variables or other configuration options by looking at the defaults and environment variable usage:
Ran tool
Ran tool
Perfect! Here's a comprehensive overview of all the arguments and parallelization options that the `mirror_tool.py` accepts:

## Command-Line Arguments

### **Parallelization & Performance Options**

1. **`--jobs N`**
   - **Purpose**: Number of parallel hashing jobs
   - **Default**: CPU count (or 4 if can't detect)
   - **Environment**: Can be set via `MIRROR_JOBS` env var
   - **Example**: `--jobs 8`

2. **`--blake3-threads N`**
   - **Purpose**: BLAKE3 internal threads per file
   - **Default**: 0 (AUTO)
   - **Environment**: Can be set via `MIRROR_B3THREADS` env var
   - **Example**: `--blake3-threads 4`

### **Algorithm & Hashing Options**

3. **`--algo {auto,blake3,sha256}`**
   - **Purpose**: Choose hash algorithm
   - **Default**: `auto` (prefers BLAKE3, falls back to SHA-256)
   - **Options**:
     - `auto`: Try BLAKE3 first, fallback to SHA-256
     - `blake3`: Force BLAKE3 (fails if not available)
     - `sha256`: Force SHA-256
   - **Example**: `--algo blake3`

4. **`--prefer-external-b3`**
   - **Purpose**: Prefer external `b3sum` command over Python BLAKE3 library
   - **Default**: False (uses Python library if available)
   - **Example**: `--prefer-external-b3`

### **Workflow Control**

5. **`--step {all,make-manifest,copy,verify}`**
   - **Purpose**: Run specific step(s)
   - **Default**: `all`
   - **Options**:
     - `all`: manifest → copy → verify
     - `make-manifest`: Only create hash manifest
     - `copy`: Only copy files with rsync
     - `verify`: Only verify hashes
   - **Example**: `--step copy`

6. **`--dry-run`**
   - **Purpose**: Preview copy operation without actually copying
   - **Applies to**: `copy` and `all` steps
   - **Example**: `--dry-run`

### **Manifest Options**

7. **`--manifest PATH`**
   - **Purpose**: Custom manifest file location
   - **Default**: 
     - For make-manifest: `SRC/BLAKE3SUMS` (or `SHA256SUMS`)
     - For verify: `DST/BLAKE3SUMS`, then `SRC/BLAKE3SUMS`
   - **Special**: Use `"-"` for stdout/stdin
   - **Example**: `--manifest /path/to/custom.manifest`

### **Positional Arguments**

8. **`src`** - Source directory path
9. **`dst`** - Destination directory path (required for copy/verify)

## Environment Variables

- **`MIRROR_JOBS`**: Set default number of parallel jobs
- **`MIRROR_B3THREADS`**: Set default BLAKE3 threads per file

## Performance Tuning Examples

```bash
# High-performance setup for NVMe drives
run-mirror --step all --jobs 16 --blake3-threads 4 --prefer-external-b3 /source /dest

# Conservative setup for HDDs
run-mirror --step all --jobs 4 --blake3-threads 1 /source /dest

# Maximum parallelization using environment variables
MIRROR_JOBS=32 MIRROR_B3THREADS=8 run-mirror --step all /source /dest

# Force SHA-256 with many jobs (if BLAKE3 unavailable)
run-mirror --step all --algo sha256 --jobs 12 /source /dest
```

## Usage Patterns

```bash
# Preview what would be copied
run-mirror --step copy --dry-run /source /dest

# Just create manifest to stdout and compress
run-mirror --step make-manifest --manifest - /source | gzip > manifest.gz

# Verify from custom manifest
run-mirror --step verify --manifest /path/to/custom.manifest /source /dest

# Two-step process: manifest first, then copy+verify
run-mirror --step make-manifest /source
run-mirror --step copy /source /dest
run-mirror --step verify /source /dest
```

⸻

##BLAKE3: External `b3sum` vs Python `blake3` Implementation

Both implementations compute the same BLAKE3 hashes, but they have different performance characteristics:

### **External `b3sum` (Recommended with `--prefer-external-b3`)**

**Advantages:**
- **Faster**: Written in Rust, highly optimized
- **Lower memory overhead**: Doesn't compete with Python for memory
- **Better CPU utilization**: Can max out CPU cores more efficiently
- **SIMD optimizations**: Takes full advantage of modern CPU vector instructions
- **No GIL issues**: Doesn't compete with Python's Global Interpreter Lock

**Installation:**
```bash
sudo apt-get install b3sum  # Ubuntu/Debian
```

### **Python BLAKE3 Implementation**

**Advantages:**
- **No external dependency**: Works out of the box if `pip install blake3`
- **Easier deployment**: One less system package to manage
- **Integration**: Runs in the same process space

**Disadvantages:**
- **Slower**: Python wrapper adds overhead
- **GIL contention**: Python's Global Interpreter Lock can limit parallelism
- **Memory competition**: Competes with Python process for memory

## Algorithm Selection Logic

### **With `--algo auto` (default):**
1. **First choice**: External `b3sum` if available
2. **Second choice**: Python BLAKE3 if installed
3. **Fallback**: SHA-256

### **With `--algo blake3 --prefer-external-b3`:**
1. **First choice**: External `b3sum` if available  
2. **Second choice**: Python BLAKE3 if installed
3. **Fails**: If neither is available

### **With `--algo blake3` (without `--prefer-external-b3`):**
1. **First choice**: Python BLAKE3 if installed
2. **Second choice**: External `b3sum` if available
3. **Fails**: If neither is available

## Recommendation for Your 70-CPU + HDD Setup

**Use external `b3sum`:**
```bash
run-mirror \
    --step all \
    --algo blake3 \
    --prefer-external-b3 \
    --jobs 4 \
    --blake3-threads 1 \
    /mnt/JCRLab/EmmaH \
    /data1/users/antonz/data/JCRLab/EmmaH
```

**Why external `b3sum` is better for your case:**

1. **CPU efficiency**: With 70 CPUs available, the external tool can utilize them better
2. **No Python overhead**: Direct system call, no interpreter overhead
3. **Memory efficiency**: Doesn't compete with Python for memory
4. **HDD-friendly**: More efficient I/O patterns for mechanical drives

**Install if needed:**
```bash
sudo apt-get update && sudo apt-get install -y b3sum
```


⸻

# Caveats in parallel transfer from HDD to multi-core CPU workstation.

For an HDD to multi-core CPU computer transfer, you need to be very careful about parallelization since HDDs are the bottleneck, not CPU power. Here are some general recommendations:

## Safe Settings for HDD Operations

### **Recommended Settings:**
```bash
run-mirror --jobs 4 --blake3-threads 1 /hdd/source /dest
```

### **Conservative Alternative:**
```bash
run-mirror --jobs 2 --blake3-threads 1 /hdd/source /dest
```

## Reasoning

### **`--jobs 4` (or even `--jobs 2`)**
- **HDD bottleneck**: HDDs have mechanical seek times and can't handle many concurrent reads efficiently
- **Sweet spot**: 2-8 concurrent operations is typically optimal for HDDs
- **Avoid**: Using all CPUs machine has bears the risk to create excessive disk head movement and actually slow things down

### **`--blake3-threads 1`**
- **Memory bandwidth**: With >20 CPUs, you could theoretically use more threads per file
- **HDD limitation**: Since the HDD is the bottleneck, additional threads per file won't help much
- **Resource efficiency**: Keeps memory usage reasonable while the disk is the limiting factor

## Progressive Testing Approach

Start conservative and test performance:

```bash
# Test 1: Very conservative
time run-mirror --jobs 2 --blake3-threads 1 --step make-manifest /hdd/source

# Test 2: Slightly more aggressive  
time run-mirror --jobs 4 --blake3-threads 1 --step make-manifest /hdd/source

# Test 3: If HDD handles it well
time run-mirror --jobs 6 --blake3-threads 1 --step make-manifest /hdd/source

# Test 4: Upper limit for HDD
time run-mirror --jobs 8 --blake3-threads 1 --step make-manifest /hdd/source
```

Monitor `iostat -x 1` during testing to see if the HDD utilization is healthy vs. thrashing.

## Full Transfer Command

```bash
# Recommended for HDD → 70 CPU system
run-mirror \
	--step all \
	--algo blake3 \
	--prefer-external-b3 \
	--jobs 4 \
	--blake3-threads 1 \
	/hdd/source \
	/workstation/dest
```

## Why Not Use All CPUs?

- **Disk thrashing**: Too many concurrent reads cause excessive seeking
- **Diminishing returns**: HDD sequential read speed is ~100-200 MB/s regardless of CPU power  
- **Resource waste**:  idle CPUs are better than a slow, thrashing HDD
- **System stability**: Keeps the system responsive for other tasks


⸻

### A) Use with a dedicated venv (no “activation” required)
	1.	Create the env once (pick where to keep envs):

```bash
mkdir -p /data1/users/antonz/envs
python3 -m venv /data1/users/antonz/envs/mirror-3.10
/data1/users/antonz/envs/mirror-3.10/bin/python -m pip install --upgrade pip

# Optional installs for speed (b3sum/blake3) and progress bar (tqdm):
# - try to get system b3sum
`sudo apt-get update && sudo apt-get install -y b3sum || true`
# - or install Python wheels
`/data1/users/antonz/envs/mirror-3.10/bin/pip install blake3 tqdm`
```

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

4.	Use it (currently my specific paths):

**Dry run** (copy preview only):

```bash
run-mirror \
  --step copy --dry-run \
  /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing/ \
  /data1/users/antonz/data/DM_summer_2025
```

**Full run** (manifest → copy → verify):

```bash
run-mirror \
  --step all --prefer-external-b3 --jobs 8 \
  /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing/ \
  /data1/users/antonz/data/DM_summer_2025
```

Just make **manifest to stdout**, then compress:

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

Create *Dockerfile* next to `mirror_tool.py`:

```Dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends rsync b3sum && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir tqdm blake3
WORKDIR /app
COPY mirror_tool.py /app/mirror_tool.py
ENTRYPOINT ["python", "/app/mirror_tool.py"]
```

**Build:**

`docker build -t mirror-b3 .`

**Run** (mount your source/dest):

**Dry run** copy:
```bash
docker run --rm \
  -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src:ro \
  -v /data1/users/antonz/data/DM_summer_2025:/dst \
  mirror-b3 --step copy --dry-run /src /dst
```

**Full run** (manifest → copy → verify):
```bash
docker run --rm \
  -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src:ro \
  -v /data1/users/antonz/data/DM_summer_2025:/dst \
  mirror-b3 --step all --prefer-external-b3 --jobs 8 /src /dst
```

**Make manifest** to host file:

```
docker run --rm \
  -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src \
  mirror-b3 --step make-manifest --manifest /src/BLAKE3SUMS /src
```

⸻

### C) “Throw‑away” one‑liner container (no local image kept)

If you don’t want to build an image, you can use python:3.11-slim ad‑hoc (slower first time). For throw‑away use you should mount the script into the container as well:

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

(Using `--rm` makes the container ephemeral.)

⸻

Notes & tips
	•	Performance: HDDs tend to like -`-jobs` *`4..8`*; NVMe can go to $(nproc).
	•	Algorithm choice:
	•	`--algo auto` (default): tries external `b3sum`, then Python `blake3`, then falls back to `sha256`.
	•	Force SHA‑256 if you must: `--algo sha256`.
	•	Manifests: by default saved as BLAKE3SUMS (or SHA256SUMS if you force sha256). Use `--manifest` - to stream.
	•	**Dry run**: only affects the copy step (preview with rsync). Manifest and verify are real actions unless you run --step copy --dry-run.

That’s it. This setup stays faithful to the “single‑purpose tools that compose” idea:
	•	pyenv (optional) picks your interpreter,
	•	venv isolates dependencies,
	•	mirror_tool.py orchestrates,
	•	b3sum/rsync do the heavy lifting,
	•	and everything pipes cleanly.


# Options to use the script by its short name without the full path:

⸻

### 1. Put it on your $PATH

If you want to type `run-mirror` from anywhere (like a real UNIX command), just make sure the script lives in a directory that’s on your PATH.

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