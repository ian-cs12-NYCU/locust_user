#!/bin/bash

echo "=========================================="
echo "Locust 快速測試腳本"
echo "=========================================="
echo ""

# 1. 檢查語法
echo "1️⃣  檢查 Python 語法..."
python3 -m py_compile locustfile.py
#!/usr/bin/env bash
set -euo pipefail

### quick_test.sh
### English, clearer, and more comprehensive quick validation script for the DN target.
### What it does:
### 1) Syntax check for `locustfile.py`.
### 2) Basic server root/connectivity check.
### 3) Scan playlist availability for video IDs 1..100 and report which are available.
### 4) For the first up to 3 available videos: fetch playlist, parse segments and run HEAD on each segment
###    to report Content-Type and Content-Length.
### 5) Do a sample of 10 random checks within 1..100.
### 6) Print a concise summary.

HOST_BASE="http://10.201.0.123"
PLAYLIST_PATH_TEMPLATE="/video/720p/video-%d/playlist.m3u8"
SEG_BASE_PATH="/video/720p"

echo "============================================================"
echo "Locust quick test (English)"
echo "NOTE: This quick test performs DNS A-record checks ONLY. (不會測試 AAAA 或 MX)"
echo "============================================================"
echo

echo "1) Python syntax check: locustfile.py"
if python3 -m py_compile locustfile.py; then
    echo "   ✅ Python syntax is valid"
else
    echo "   ❌ Python syntax error in locustfile.py"
    exit 1
fi
echo

echo "2) Server root/connectivity check"
if curl -s -o /dev/null -w "%{http_code} - %{time_total}s" --max-time 5 "${HOST_BASE}/" | grep -q "^200"; then
    echo "   ✅ Server root is reachable"
else
    echo "   ❌ Server root is not reachable or returned non-200"
    exit 1
fi
echo

echo "3) Scan playlist availability for video IDs 1..100"
available=()
for i in $(seq 1 100); do
    url="${HOST_BASE}$(printf "${PLAYLIST_PATH_TEMPLATE}" "$i")"
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url" || echo "000")
        if [ "$code" = "200" ]; then
            available+=("$i")
            printf "  ✅ Found: video-%s (200)\n" "$i"
        fi
done

echo
echo "   Summary: found ${#available[@]} available videos in range 1..100"
if [ ${#available[@]} -eq 0 ]; then
    echo "   No playlists found in 1..100. Please verify the DN server or the path structure."
    exit 1
fi
echo

max_check=3
count=0
echo "4) For up to ${max_check} available videos, fetch playlist and validate segments"
for vid in "${available[@]}"; do
    if [ $count -ge $max_check ]; then
        break
    fi
    count=$((count+1))
    playlist_url="${HOST_BASE}$(printf "${PLAYLIST_PATH_TEMPLATE}" "$vid")"
    echo
    echo "=== video-${vid} ==="
    echo "Playlist URL: ${playlist_url}"

    playlist_content=$(curl -s --max-time 5 "$playlist_url" || true)
        if [ -z "$playlist_content" ]; then
            echo "  ❌ FAIL: empty playlist or fetch failed"
        continue
    fi

    # extract non-comment, non-empty lines (segment references)
    mapfile -t segments < <(printf "%s" "$playlist_content" | awk 'NF && $0 !~ /^#/ { print $0 }')

    echo "  Parsed ${#segments[@]} segments from playlist"
    if [ ${#segments[@]} -eq 0 ]; then
        echo "  WARN: no segments found in playlist"
        continue
    fi

            for seg in "${segments[@]}"; do
                # normalize relative paths like ../../seg-123.ts -> take basename and build full path
                segfile=$(basename "$seg")
                seg_url="${HOST_BASE}${SEG_BASE_PATH}/${segfile}"
                # Use HEAD to get metadata
                headers=$(curl -s -I --max-time 5 "$seg_url" || true)
                # remove CRs for consistent parsing
                headers_clean=$(printf "%s" "$headers" | tr -d '\r')
                code=$(printf "%s" "$headers_clean" | head -n1 | awk '{print $2}' || echo "000")
                ctype=$(printf "%s" "$headers_clean" | grep -i '^Content-Type:' | sed -E 's/^[^:]+:[[:space:]]*//' || echo "-")
                clen=$(printf "%s" "$headers_clean" | grep -i '^Content-Length:' | sed -E 's/^[^:]+:[[:space:]]*//' || echo "-")
                # Print a clean, consistent line per segment
                if [ "$code" = "200" ]; then
                    printf "    ✅ Segment: %-20s | HTTP: %-3s | Content-Type: %-20s | Content-Length: %s\n" "$segfile" "$code" "$ctype" "$clen"
                else
                    printf "    ❌ Segment: %-20s | HTTP: %-3s | Content-Type: %-20s | Content-Length: %s\n" "$segfile" "$code" "$ctype" "$clen"
                fi
            done
done

echo
echo "5) Random sample checks (10 samples in 1..100)"
for i in $(seq 1 10); do
    rand=$(( (RANDOM % 100) + 1 ))
    url="${HOST_BASE}$(printf "${PLAYLIST_PATH_TEMPLATE}" "$rand")"
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url" || echo "000")
    if [ "$code" = "200" ]; then
        printf "  ✅ Sample %2d: video-%3d -> HTTP %s\n" "$i" "$rand" "$code"
    else
        printf "  ❌ Sample %2d: video-%3d -> HTTP %s\n" "$i" "$rand" "$code"
    fi
done

echo
echo "============================================================"
echo "6) DNS checks for domains used by locust"

# determine dns server from profiles/config-users.json if present (DnsLoad entry)
DNS_SERVER="1.1.1.1"
if [ -f "profiles/config-users.json" ]; then
    ln=$(grep -n '"user_class_name"[[:space:]]*:[[:space:]]*"DnsLoad"' -n profiles/config-users.json | cut -d: -f1 | head -n1 || true)
    if [ -n "$ln" ]; then
        dns_line=$(sed -n "$ln,$((ln+10))p" profiles/config-users.json | grep '"dns_server"' | head -n1 || true)
        if [ -n "$dns_line" ]; then
            DNS_SERVER=$(echo "$dns_line" | sed -E 's/.*"dns_server"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
        fi
    fi
fi

# determine a small sample of IPs in 10.201.0.0/16 to check (prefer configured host if 10.201.*)
echo "DNS server to test: ${DNS_SERVER}"

# Build a small sample of IPs using the project's TargetServerManager to better mirror Locust allocation.
# We call a small Python snippet that imports the project's helper and requests a few target servers for VideoUser.
# Any informational prints from the manager are silenced when importing to keep output clean.
sample_ips=()
py_out=$(python3 - <<'PY'
import os, sys
from contextlib import redirect_stdout
with open(os.devnull, 'w') as devnull:
    with redirect_stdout(devnull):
        from utils.target_server import get_target_servers
        ips = get_target_servers('VideoUser', 4)
        # print the IPs (silenced prints during manager init are redirected)
        print(' '.join(ips))
PY
)
if [ -n "$py_out" ]; then
    # split into bash array
    read -r -a sample_ips <<< "$py_out"
fi
# Fallback: if python did not return usable IPs, use a few deterministic samples
if [ ${#sample_ips[@]} -eq 0 ]; then
    sample_prefix="10.201"
    sample_ips+=("${sample_prefix}.0.1" "${sample_prefix}.0.50" "${sample_prefix}.0.200")
fi

echo
echo "Sample IP reachability checks (few addresses in 10.201.0.0/16): ${sample_ips[*]}"
for sip in "${sample_ips[@]}"; do
    # check HTTP root on the IP
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://${sip}/" || echo "000")
    if [ "$code" = "200" ]; then
        printf "  ✅ %-15s -> HTTP %s\n" "$sip" "$code"
    elif [ "$code" = "000" ]; then
        printf "  ❌ %-15s -> unreachable or timeout\n" "$sip"
    else
        printf "  ⚠️  %-15s -> HTTP %s\n" "$sip" "$code"
    fi
done

# extract domains list from locustfile.py
domains=()
mapfile -t raw_domains < <(awk '/domains = \[/{flag=1;next}/\]/{flag=0}flag{print}' locustfile.py || true)
for d in "${raw_domains[@]}"; do
    dom=$(echo "$d" | sed -E 's/[^\"]*"([^"]+)".*$/\1/')
    if [ -n "$dom" ]; then
        domains+=("$dom")
    fi
done

if [ ${#domains[@]} -eq 0 ]; then
    echo "No domains found in locustfile.py to test."
else
    echo "Testing DNS for domains used in locustfile.py: ${domains[*]}"
    types=(A)
    for domain in "${domains[@]}"; do
        echo
        printf "Domain: %s\n" "$domain"
        for t in "${types[@]}"; do
            if command -v dig >/dev/null 2>&1; then
                out=$(dig +short @${DNS_SERVER} ${domain} ${t} 2>/dev/null | tr -s '\n' ' ')
            else
                # fallback to nslookup for A/MX; nslookup doesn't support AAAA query type flag uniformly
                if [ "$t" = "A" ] || [ "$t" = "MX" ]; then
                    out=$(nslookup -type=${t} ${domain} ${DNS_SERVER} 2>/dev/null | awk '/^\s*[^#].*\bAddress:/{print $2}' | tr -s '\n' ' ')
                else
                    out="(no tool to query ${t})"
                fi
            fi
            if [ -n "$out" ]; then
                printf "  ✅ %-4s -> %s\n" "$t" "$out"
            else
                printf "  ❌ %-4s -> no answer\n" "$t"
            fi
        done
    done
fi

echo
echo "============================================================"
echo "測試摘要"
echo "  - 目標主機: ${HOST_BASE}"
echo "  - 在 1..100 範圍內找到的 playlist 數量: ${#available[@]}"
echo "  - 範例可用 ID: ${available[@]:0:10}"
echo "============================================================"
echo
echo "建議執行小型 Locust 測試："
echo "  locust -f locustfile.py --host ${HOST_BASE} --users 3 --spawn-rate 1 --run-time 1m --headless"
echo
