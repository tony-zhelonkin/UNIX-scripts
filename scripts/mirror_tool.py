#!/usr/bin/env python3
"""
Mirror a directory with a content-hash manifest and verification.

Design goals (Unix-y):
- Single-purpose steps: make-manifest, copy, verify (or all).
- Optional deps: blake3/tqdm are optional; sha256 + no bar fallback.
- Pipeable: --manifest - allows stdout/stdin for chaining/compression.
- Clear exit codes: 0 ok, 1 verify failed, 2 usage/IO errors.
"""

from __future__ import annotations
import argparse, os, sys, time, subprocess, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Tuple
from shutil import which

# --- Optional deps ---
try:
    from blake3 import blake3 as blake3_hasher  # type: ignore
    HAVE_BLAKE3 = True
except Exception:
    blake3_hasher = None  # type: ignore
    HAVE_BLAKE3 = False

try:
    from tqdm import tqdm  # type: ignore
    HAVE_TQDM = True
except Exception:
    tqdm = None  # type: ignore
    HAVE_TQDM = False

# --- Defaults & filters ---
EXCLUDES = {'.DS_Store'}
EXCLUDE_PREFIXES = ('._',)

# --- Helpers for external tools ---
def have_cmd(name: str) -> bool:
    return which(name) is not None

def b3sum_one(path: Path) -> str:
    """Return hex digest using external `b3sum`."""
    out = subprocess.check_output(['b3sum', str(path)], text=True)
    # format is "<hash>  <path>\n"
    return out.split()[0]

# --- File iteration ---
def iter_rel_files(root: Path) -> Iterable[Path]:
    for p in root.rglob('*'):
        if p.is_file():
            n = p.name
            if n in EXCLUDES or n.startswith(EXCLUDE_PREFIXES):
                continue
            yield p.relative_to(root)

# --- Hashers ---
def sha256_file(path: Path, chunk: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def blake3_file_py(path: Path, max_threads: int = 0, chunk: int = 4 * 1024 * 1024) -> str:
    """BLAKE3 via Python binding; max_threads: 0 -> AUTO."""
    if not HAVE_BLAKE3:
        raise RuntimeError("blake3 module not available")
    h = blake3_hasher(max_threads=max_threads)
    with path.open('rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

# --- Progress wrapper ---
class Progress:
    def __init__(self, total: int, desc: str):
        self.total = total
        self.count = 0
        self.desc = desc
        self.use_bar = HAVE_TQDM and sys.stderr.isatty()
        if self.use_bar:
            self.bar = tqdm(total=total, unit='file', desc=desc, file=sys.stderr)
        else:
            self.bar = None
            print(f"{desc}: {total} files", file=sys.stderr)

    def update(self, n: int = 1):
        self.count += n
        if self.use_bar:
            self.bar.update(n)  # type: ignore
        elif self.count % 100 == 0 or self.count == self.total:
            print(f"{self.desc}: {self.count}/{self.total}", file=sys.stderr)

    def close(self):
        if self.use_bar and self.bar:
            self.bar.close()  # type: ignore

# --- Manifest I/O ---
def write_manifest(
    src: Path,
    manifest_out: str,
    algo: str,
    jobs: int,
    b3threads: int,
    prefer_external_b3: bool,
) -> None:
    files = list(iter_rel_files(src))
    prog = Progress(len(files), "Hashing")

    # choose hasher function
    use_b3sum = (algo == 'blake3' and prefer_external_b3 and have_cmd('b3sum'))
    use_b3py  = (algo == 'blake3' and not use_b3sum and HAVE_BLAKE3)
    if algo == 'auto':
        if have_cmd('b3sum'):
            use_b3sum = True
        elif HAVE_BLAKE3:
            use_b3py = True
        else:
            algo = 'sha256'  # fallback

    if algo == 'sha256':
        def _hash(path: Path) -> str:
            return sha256_file(path)
    elif use_b3sum:
        def _hash(path: Path) -> str:
            return b3sum_one(path)
    elif use_b3py:
        def _hash(path: Path) -> str:
            return blake3_file_py(path, max_threads=b3threads)
    else:
        # last-chance fallback
        def _hash(path: Path) -> str:
            return sha256_file(path)

    # open output (stdout if "-")
    outfh = sys.stdout if manifest_out == '-' else open(manifest_out, 'w', encoding='utf-8')
    try:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(_hash, src / rp): rp for rp in files}
            for fut in as_completed(futs):
                rp = futs[fut]
                digest = fut.result()
                outfh.write(f"{digest}  {rp.as_posix()}\n")
                prog.update(1)
    finally:
        prog.close()
        if outfh is not sys.stdout:
            outfh.close()

def parse_manifest_line(line: str) -> Tuple[str, Path]:
    # "<hash>  <path>"
    digest, rp = line.split(None, 1)
    return digest, Path(rp.strip())

def iter_manifest(manifest_in: str) -> Iterable[Tuple[str, Path]]:
    infh = sys.stdin if manifest_in == '-' else open(manifest_in, 'r', encoding='utf-8')
    try:
        for line in infh:
            line = line.rstrip('\n')
            if not line:
                continue
            yield parse_manifest_line(line)
    finally:
        if infh is not sys.stdin:
            infh.close()

def verify_manifest(
    target: Path,
    manifest_in: str,
    algo: str,
    jobs: int,
    b3threads: int,
    prefer_external_b3: bool,
) -> int:
    pairs = list(iter_manifest(manifest_in))
    prog = Progress(len(pairs), "Verifying")

    # choose hasher
    use_b3sum = (algo == 'blake3' and prefer_external_b3 and have_cmd('b3sum'))
    use_b3py  = (algo == 'blake3' and not use_b3sum and HAVE_BLAKE3)
    if algo == 'auto':
        if have_cmd('b3sum'):
            use_b3sum = True
        elif HAVE_BLAKE3:
            use_b3py = True
        else:
            algo = 'sha256'
    if algo == 'sha256':
        def _hash(path: Path) -> str:
            return sha256_file(path)
    elif use_b3sum:
        def _hash(path: Path) -> str:
            return b3sum_one(path)
    elif use_b3py:
        def _hash(path: Path) -> str:
            return blake3_file_py(path, max_threads=b3threads)
    else:
        def _hash(path: Path) -> str:
            return sha256_file(path)

    errors = 0
    def check_one(pair: Tuple[str, Path]):
        expect, rp = pair
        p = target / rp
        if not p.exists():
            return (rp, 'MISSING', expect, '')
        got = _hash(p)
        if got != expect:
            return (rp, 'MISMATCH', expect, got)
        return None

    try:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            for res in ex.map(check_one, pairs):
                if res:
                    errors += 1
                    rp, kind, expect, got = res
                    print(f"[{kind}] {rp}", file=sys.stderr)
                prog.update(1)
    finally:
        prog.close()

    return errors

def rsync_copy(src: Path, dst: Path, dry_run: bool) -> None:
    cmd = ['rsync', '-a', '--info=stats2,progress2', f"{src}/", f"{dst}/"]
    if dry_run:
        cmd.insert(2, '--dry-run')
    subprocess.check_call(cmd)

# --- CLI ---
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Mirror with content manifest and verification"
    )
    # sub = ap.add_subparsers(dest='cmd')

    # Common args
    ap.add_argument('--jobs', type=int, default=int(os.environ.get('MIRROR_JOBS', os.cpu_count() or 4)),
                    help='parallel hashing jobs (default: CPU count)')
    ap.add_argument('--blake3-threads', type=int, default=int(os.environ.get('MIRROR_B3THREADS', 0)),
                    help='BLAKE3 internal threads per file (0=AUTO)')
    ap.add_argument('--algo', choices=('auto', 'blake3', 'sha256'), default='auto',
                    help='hash algorithm: auto (prefer blake3), blake3, or sha256')
    ap.add_argument('--prefer-external-b3', action='store_true',
                    help='prefer external b3sum if available')
    ap.add_argument('--manifest', default=None,
                    help='manifest path; for make-manifest: write here (default SRC/BLAKE3SUMS). '
                         'For verify: read from here (default DST/BLAKE3SUMS, else SRC/BLAKE3SUMS). '
                         'Use "-" for stdout/stdin.')

    # Steps
    # all
    ap.add_argument('--dry-run', action='store_true', help='dry-run for copy/all')
    ap.add_argument('--step', choices=('all', 'make-manifest', 'copy', 'verify'), default='all',
                    help='run a single step or all (default)')

    # positional
    ap.add_argument('src', type=Path, nargs='?')
    ap.add_argument('dst', type=Path, nargs='?')

    args = ap.parse_args()

    ts = time.strftime('%Y%m%d-%H%M%S')
    print(f"=== Mirror ===\nTime : {ts}\nStep : {args.step}\nDry  : {args.dry_run}\nAlgo : {args.algo}\n",
          file=sys.stderr)

    try:
        if args.step in ('all', 'make-manifest'):
            if not args.src:
                print("SRC required for make-manifest", file=sys.stderr)
                return 2
            mf_out = args.manifest or str(args.src / ('BLAKE3SUMS' if args.algo != 'sha256' else 'SHA256SUMS'))
            print(f"[1/3] Creating manifest at source → {mf_out}", file=sys.stderr)
            write_manifest(args.src, mf_out, args.algo, args.jobs, args.blake3_threads, args.prefer_external_b3)

        if args.step in ('all', 'copy'):
            if not (args.src and args.dst):
                print("SRC and DST required for copy", file=sys.stderr)
                return 2
            print("[2/3] Copying with rsync...", file=sys.stderr)
            rsync_copy(args.src, args.dst, args.dry_run)
            if args.dry_run and args.step == 'copy':
                print("[OK] Dry-run complete.", file=sys.stderr)
                return 0

        if args.step in ('all', 'verify'):
            # Decide manifest to use
            if args.manifest:
                mf_in = args.manifest
            else:
                default_name = 'BLAKE3SUMS' if args.algo != 'sha256' else 'SHA256SUMS'
                candidate = (args.dst / default_name) if args.dst else None
                if candidate and candidate.exists():
                    mf_in = str(candidate)
                else:
                    # fallback to SRC with same default_name
                    if not args.src:
                        print("Need SRC or --manifest for verify", file=sys.stderr)
                        return 2
                    mf_in = str(args.src / default_name)

            # Decide target directory to verify against
            target = args.dst if args.dst else args.src
            if not target:
                print("Need DST or SRC for verify target", file=sys.stderr)
                return 2

            print(f"[3/3] Verifying at {target} using {mf_in}", file=sys.stderr)
            errs = verify_manifest(target, mf_in, args.algo, args.jobs, args.blake3_threads, args.prefer_external_b3)
            if errs:
                print(f"[ERROR] Verification failed: {errs} problem(s).", file=sys.stderr)
                return 1
            print("[OK] Verification successful.", file=sys.stderr)

        return 0

    except KeyboardInterrupt:
        print("[ERROR] Interrupted.", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())