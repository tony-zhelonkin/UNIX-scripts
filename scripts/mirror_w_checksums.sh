#!/usr/bin/env bash
set -Eeuo pipefail

# Mirror a directory with checksum verification.
# Usage:
#   ./mirror_with_checksums.sh [--dry-run] /source/dir /destination/dir

DRYRUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRYRUN=1
  shift
fi

SRC="${1:?Missing source directory}"
DST="${2:?Missing destination directory}"

TS="$(date +'%Y%m%d-%H%M%S')"
LOG_DIR_GLOBAL="${HOME}/mirror_logs"
LOG_DIR_LOCAL="${DST}/mirror_logs"
mkdir -p "$LOG_DIR_GLOBAL" "$LOG_DIR_LOCAL"

LOG_FILE="${LOG_DIR_GLOBAL}/mirror_${TS}.log"
LOG_FILE_LOCAL="${LOG_DIR_LOCAL}/mirror_${TS}.log"

# helper to tee to both logs
tee2() { tee -a "$LOG_FILE" | tee -a "$LOG_FILE_LOCAL" >/dev/null; }

echo "=== Mirror with checksums ===" | tee2
echo "Time: $TS" | tee2
echo "Source: $SRC" | tee2
echo "Dest  : $DST" | tee2
[[ $DRYRUN -eq 1 ]] && echo "Mode  : DRY-RUN" | tee2

# 1) Build manifest at source (relative paths, SHA-256)
if [[ $DRYRUN -eq 0 ]]; then
  echo "[1/3] Creating manifest at source..." | tee2
  (
    cd "$SRC"
    find . -type f -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 sha256sum > SHA256SUMS.tmp
    mv -f SHA256SUMS.tmp SHA256SUMS
  )
  echo "[OK] Manifest written: $SRC/SHA256SUMS" | tee2
else
  echo "[1/3] Skipping manifest creation (dry-run)" | tee2
fi

# 2) Copy entire tree with rsync
echo "[2/3] Copying tree with rsync..." | tee2
if [[ $DRYRUN -eq 1 ]]; then
  rsync -a --dry-run --info=stats2,progress2 "$SRC"/ "$DST"/ | tee2
  echo "[OK] Dry-run complete. No files copied." | tee2
  exit 0
else
  rsync -a --info=progress2 "$SRC"/ "$DST"/ | tee2
fi

# 3) Verify checksums at destination
echo "[3/3] Verifying at destination..." | tee2
(
  cd "$DST"
  if sha256sum -c SHA256SUMS | tee2; then
    echo "[OK] Verification successful!" | tee2
  else
    echo "[ERROR] Verification failed. See logs:" | tee2
    echo "  - $LOG_FILE" | tee2
    echo "  - $LOG_FILE_LOCAL" | tee2
    exit 1
  fi
)
