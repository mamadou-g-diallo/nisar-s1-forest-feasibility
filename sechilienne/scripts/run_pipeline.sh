#!/usr/bin/env bash
# Resumable landslide pipeline (Séchilienne), meant to run as a systemd *user* service so that it
# survives the closing of the desktop application and restarts after a failure:
#
#   bash sechilienne/scripts/run_pipeline.sh --install     # create + start the service
#   systemctl --user status gl-pipeline                   # state
#   journalctl --user -u gl-pipeline -f                   # follow
#
# Every step is idempotent: downloads skip complete SAFEs and resume partial files, SNAP skips
# finished pairs and deletes incomplete outputs, the analysis is recomputed from files on disk.
# Memory is capped (8 GB machine): an out-of-memory kill then hits SNAP, not the desktop session.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DATA=/media/dell/Transcend1/nisar_data/sechilienne
LOGS="$DATA/logs"
PY=/home/dell/anaconda3/envs/nisar_s1/bin/python
UNIT=gl-pipeline

if [[ "${1:-}" == "--install" ]]; then
  mkdir -p "$LOGS"
  systemctl --user stop "$UNIT" 2>/dev/null || true
  systemctl --user reset-failed "$UNIT" 2>/dev/null || true
  systemd-run --user --unit="$UNIT" --working-directory="$REPO" \
    --setenv=PATH="$(dirname "$PY"):/usr/bin:/bin" --setenv=HOME="$HOME" \
    --setenv=_JAVA_OPTIONS=-Xmx${GL_XMX:-2800m} --setenv=SNAP_CACHE_GB=1 \
    -p MemoryHigh=3G -p MemoryMax=3500M -p MemorySwapMax=1G -p OOMScoreAdjust=900 \
    -p Restart=on-failure -p RestartSec=120 -p StartLimitIntervalSec=0 \
    bash "$REPO/scripts/glissement/run_pipeline.sh"
  echo "service $UNIT lancé ; journaux dans $LOGS"
  exit 0
fi

mkdir -p "$LOGS"
cd "$REPO"
state() { echo "$(date '+%F %T') $*" | tee -a "$LOGS/pipeline_state.txt"; }

state "début (reprise éventuelle)"
state "g2 téléchargement Sentinel-1 (4 flux : 2 orbites x 2 lots ; légers en mémoire)"
pids=()
for o in 161 139; do
  for sh in 0 1; do
    "$PY" -u sechilienne/scripts/g2_fetch_s1.py --orbit "$o" --shard "$sh/2" >> "$LOGS/g2_${o}_${sh}.log" 2>&1 &
    pids+=($!)
  done
done
for p in "${pids[@]}"; do wait "$p" || true; done   # completeness is checked just below
n_part=$(find "$DATA/sentinel1" -maxdepth 2 -name "*.SAFE.part" | wc -l)
if (( n_part > 0 )); then state "ÉCHEC : $n_part SAFE incomplets"; exit 1; fi
state "g3 interférogrammes SNAP"
"$PY" -u sechilienne/scripts/g3_process_s1.py --wait-h 0 >> "$LOGS/g3.log" 2>&1
n_ifg=$(find "$DATA/processed/sentinel1" -name "ifg_*.dim" ! -name "*_part.dim" | wc -l)
state "g3 : $n_ifg interférogrammes présents"
if (( n_ifg < 17 )); then state "ÉCHEC : interférogrammes manquants"; exit 1; fi
state "g4 analyse L contre C"
"$PY" -u sechilienne/scripts/g4_analysis.py >> "$LOGS/g4.log" 2>&1
state "TERMINÉ"
