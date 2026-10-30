#!/bin/bash
# Relay an SMS code to a waiting vfs-register run: ./probe/send_otp.sh 123456
set -e
cd "$(dirname "$0")/.."
source .env
enc=$(printf '%s:%s' "$(date +%s)" "$1" | VFS_PASSWORD="$VFS_PASSWORD" openssl enc -aes-256-cbc -pbkdf2 -a -A -pass env:VFS_PASSWORD)
args=(-X PUT repos/dijiclick/visa-slots/contents/otp.txt -f message=otp -f branch=otp -f content="$(printf '%s' "$enc" | base64)")
if sha=$(gh api "repos/dijiclick/visa-slots/contents/otp.txt?ref=otp" -q .sha 2>/dev/null); then args+=(-f sha="$sha"); fi
gh api "${args[@]}" -q .commit.sha
