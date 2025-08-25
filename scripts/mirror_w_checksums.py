#!/usr/bin/env python3
import argparse, os, sys, hashlib, concurrent.futures, mmap, time
from pathlib import Path
from blake3 import blake3
from tqdm import tqdm
import subprocess

EXCLUDES = {'.DS_Store'}
EXCLUDE_PREFIXES = ('._',)

def relpaths(root: Path):
    for p in root.rglob('*'):
        if p.is_file():
            name = p.name
            if name in EXCLUDES or name.startswith(EXCLUDE_PREFIXES):
                continue
            yield p.relative_to(root)

def hash_file(path: Path, max_threads: int = 0, chunk: int = 4*1024*1024):
    # mmap + streaming to keep memory modest; BLAKE3 can also mmap entire file.
    h = blake3(max_threads=max_threads)
    with path.open('rb') as f:
        # On very large files, plain read loop is often fine; mmap may help.
        data = f.read(chunk)
        while data:
            h.update(data)
            data = f.read(chunk)
    return h.hexdigest()

def write_manifest(src: Path, manifest: Path, jobs: int, max_threads: int):
    files = list(relpaths(src))
    manifest_tmp = manifest.with_suffix(manifest.suffix + '.tmp')
    with tqdm(total=len(files), unit='file', desc='Hashing (BLAKE3)') as bar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(hash_file, src / rp, max_threads): rp for rp in files}
            with manifest_tmp.open('w', encoding='utf-8') as out:
                for fut in concurrent.futures.as_completed(futs):
                    rp = futs[fut]
                    digest = fut.result()
                    # match `sum`-tool formatting: "<hash><space><space><path>"
                    out.write(f"{digest}  {rp.as_posix()}\n")
                    bar.update(1)
    manifest_tmp.replace(manifest)

def verify_manifest(dst: Path, manifest: Path, jobs: int, max_threads: int) -> int:
    lines = manifest.read_text(encoding='utf-8').splitlines()
    pairs = []
    for line in lines:
        if not line.strip(): continue
        # split once from the left: "HASH  path"
        digest, rp = line.split(None, 1)
        # rp may still have leading spaces if paths contained spaces; format above avoids that.
        rp = rp.strip()
        pairs.append((digest, Path(rp)))

    errors = 0
    def check_one(pair):
        expect, rp = pair
        p = dst / rp
        if not p.exists():
            return (rp, 'MISSING', expect, '')
        got = hash_file(p, max_threads=max_threads)
        if got != expect:
            return (rp, 'MISMATCH', expect, got)
        return None

    with tqdm(total=len(pairs), unit='file', desc='Verifying (BLAKE3)') as bar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
            for res in ex.map(check_one, pairs):
                if res:
                    errors += 1
                    rp, kind, expect, got = res
                    sys.stderr.write(f"[{kind}] {rp}\n")
                bar.update(1)
    return errors

def rsync_copy(src: Path, dst: Path, dry_run: bool):
    cmd = ['rsync', '-a', '--info=stats2,progress2', f"{src}/", f"{dst}/"]
    if dry_run:
        cmd.insert(2, '--dry-run')
    subprocess.check_call(cmd)

def main():
    ap = argparse.ArgumentParser(description='Mirror with BLAKE3 manifest + verify')
    ap.add_argument('src', type=Path)
    ap.add_argument('dst', type=Path)
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 4, help='parallel file hashing jobs')
    ap.add_argument('--blake3-threads', type=int, default=0, help='BLAKE3 internal threads per file (0=AUTO)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    ts = time.strftime('%Y%m%d-%H%M%S')
    log_global = Path.home()/ 'mirror_logs'
    log_local = args.dst / 'mirror_logs'
    log_global.mkdir(parents=True, exist_ok=True)
    log_local.mkdir(parents=True, exist_ok=True)
    print(f"=== Mirror with BLAKE3 ===\nTime: {ts}\nSource: {args.src}\nDest  : {args.dst}\nDry   : {args.dry-run}")

    manifest = args.src / 'BLAKE3SUMS'

    if args.dry_run:
        print("[1/3] Skipping manifest (dry-run)")
    else:
        print(f"[1/3] Creating manifest at source (jobs={args.jobs}, b3threads={args.blake3_threads})")
        write_manifest(args.src, manifest, jobs=args.jobs, max_threads=args.blake3_threads)

    print("[2/3] Copying with rsync...")
    rsync_copy(args.src, args.dst, args.dry_run)
    if args.dry_run:
        print("[OK] Dry-run complete.")
        return

    print("[3/3] Verifying at destination...")
    errs = verify_manifest(args.dst, args.dst / 'BLAKE3SUMS', jobs=args.jobs, max_threads=args.blake3_threads) \
           if (args.dst / 'BLAKE3SUMS').exists() else \
           verify_manifest(args.dst, manifest, jobs=args.jobs, max_threads=args.blake3_threads)
    if errs:
        print(f"[ERROR] Verification failed: {errs} problem(s).", file=sys.stderr)
        sys.exit(1)
    print("[OK] Verification successful.")

if __name__ == '__main__':
    main()