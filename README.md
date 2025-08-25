# UNIX scripts 

## 'mirror_w_checksums.py'

Python‑orchestrated (BLAKE3 + parallel + progress). Keep rsync for copying; do hashing/verification in Python using the blake3 wheels (no Rust toolchain needed). You can run this either in a venv or a tiny Docker image.

#### Option - A: venv

```bash
python3 -m venv ~/mirrorenv
source ~/mirrorenv/bin/activate
pip install --upgrade pip blake3 tqdm
```

To run:
```
# Dry run (preview copy only)
python mirror_blake3.py \
  /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing \
  /data1/users/antonz/data/MogilenkoLab_sequensing \
  --dry-run

# Real run with modest parallelism (e.g., 8 hashing workers, 0 = AUTO threads per file)
python mirror_blake3.py \
  /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing \
  /data1/users/antonz/data/MogilenkoLab_sequensing \
  --jobs 8 --blake3-threads 0
```

#### Option - B: docker/podman

Create Dockerfile:
```Dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends rsync && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir blake3 tqdm
WORKDIR /app
COPY mirror_blake3.py /app/mirror_blake3.py
ENTRYPOINT ["python", "/app/mirror_blake3.py"]
```

Build & run (mount your host paths):
```
# build
docker build -t mirror-b3 .

# dry run
docker run --rm -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src:ro \
               -v /data1/users/antonz/data/MogilenkoLab_sequensing:/dst \
               mirror-b3 /src /dst --dry-run

# real run
docker run --rm -v /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing:/src:ro \
               -v /data1/users/antonz/data/MogilenkoLab_sequensing:/dst \
               mirror-b3 /src /dst --jobs 8 --blake3-threads 0
```

If you prefer rootless, use podman run the same way.


## `mirror_w_checksums.sh`

Very slow 

Makes a manifest with SHA-256 checksums, copies with rsync, and verifies at the destination

# How to use

### Real run (creates manifest, copies, verifies):

```bash
./mirror_with_checksums.sh /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing /data1/users/antonz/data/MogilenkoLab_sequensing
```

### Dry run (shows what would be copied, no manifest/verify):

```bash
./mirror_with_checksums.sh --dry-run /mnt/DMLabHD5Tb1/MogilenkoLab_sequensing /data1/users/antonz/data/MogilenkoLab_sequensing
```


