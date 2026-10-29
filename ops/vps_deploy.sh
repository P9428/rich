#!/usr/bin/env bash
# Deploys the rich engine (src/duval.py) to the VPS as a capped systemd service, in parallel with the home machine.
# Ruled decisions/2026-10-29-checklist-tape-outage: the host is the limiting factor (a laptop that hard-crashed three times in six days,
# tape in 17 of 24 hours on 10-28). The VPS has been up 74 days and answers the Solana RPC in 86 ms against 860 ms from the laptop.
#
# The VPS copy writes its own journal under /srv/rich; nothing is merged and nothing is counted until the parallel day is compared
# (ops/tape_compare.py) and a cut-over is ruled. Resource caps mirror pmcapture so the box protects its live services.
#
# Run from C:\Users\newce\rich in Git Bash:   bash ops/vps_deploy.sh
# Re-running is safe: it re-copies the code and restarts the service.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY=/c/Users/newce/.ssh/id_ed25519
H=root@66.135.15.102
SSH="ssh -o ConnectTimeout=20 -o IdentitiesOnly=yes -i $KEY"
SCP="scp -o ConnectTimeout=20 -o IdentitiesOnly=yes -i $KEY"

$SSH $H 'mkdir -p /srv/rich/src /srv/rich/ops /srv/rich/prereg /srv/rich/journal/paths /srv/rich/journal/news /srv/rich/state /srv/rich/monitor /srv/rich/out; test -x /srv/rich/venv/bin/python || (python3 -m venv /srv/rich/venv && /srv/rich/venv/bin/pip install -q websockets)'
$SCP src/common.py src/duval.py $H:/srv/rich/src/
$SCP prereg/CONTRACT.md $H:/srv/rich/prereg/
$SCP ops/vps/rich_guard.py $H:/srv/rich/ops/
$SCP ops/vps/rich-duval.service ops/vps/rich-guard.service ops/vps/rich-guard.timer $H:/etc/systemd/system/
$SSH $H 'systemctl daemon-reload && systemctl enable rich-duval.service rich-guard.timer >/dev/null 2>&1; systemctl restart rich-duval.service; systemctl start rich-guard.timer; sleep 20; echo "service: $(systemctl is-active rich-duval) timer: $(systemctl is-active rich-guard.timer)"; tr -d "\n " < /srv/rich/monitor/heartbeat.json 2>/dev/null; echo; tail -3 /srv/rich/monitor/sensor-stderr.log 2>/dev/null; systemctl show rich-duval -p MemoryCurrent --value | awk "{printf \"mem %.0f MB\n\", \$1/1048576}"'
echo "deployed. Check later with:  bash ops/vps_pull.sh && python ops/tape_compare.py"
