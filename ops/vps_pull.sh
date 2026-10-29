#!/usr/bin/env bash
# Pulls the VPS engine's tape and monitor files into journal/vps/ (gitignored) for ops/tape_compare.py.
# Read-only against the VPS. Run from C:\Users\newce\rich:   bash ops/vps_pull.sh [YYYY-MM-DD]
# Without a date it pulls today (UTC) and yesterday. Each file is re-copied whole (no rsync on this machine), about 60 MB a day.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY=/c/Users/newce/.ssh/id_ed25519
H=root@66.135.15.102
SCP="scp -o ConnectTimeout=20 -o IdentitiesOnly=yes -i $KEY"
mkdir -p journal/vps/paths journal/vps/news journal/vps/monitor
if [ $# -ge 1 ]; then DAYS="$*"; else DAYS="$(date -u +%F) $(date -u -d yesterday +%F 2>/dev/null || date -u -v-1d +%F)"; fi
for d in $DAYS; do
  $SCP "$H:/srv/rich/journal/paths/$d.jsonl" journal/vps/paths/ 2>/dev/null || echo "no paths for $d on the VPS"
  $SCP "$H:/srv/rich/journal/news/$d.jsonl" journal/vps/news/ 2>/dev/null || true
done
$SCP "$H:/srv/rich/journal/launches.jsonl" "$H:/srv/rich/journal/events.jsonl" "$H:/srv/rich/journal/paper.jsonl" journal/vps/ 2>/dev/null || true
$SCP "$H:/srv/rich/monitor/heartbeat.json" "$H:/srv/rich/monitor/guard.log" "$H:/srv/rich/monitor/feed-errors.log" journal/vps/monitor/ 2>/dev/null || true
ls -la journal/vps journal/vps/paths
