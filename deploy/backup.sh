#!/usr/bin/env sh
set -eu

project_dir=${1:-/home/ubuntu/paper-reading-assistant}
backup_dir=${2:-/home/ubuntu/backups/paper-reading-assistant}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

mkdir -p "$backup_dir"
tar -C "$project_dir" -czf "$backup_dir/paper-reader-$timestamp.tar.gz" data

find "$backup_dir" -type f -name 'paper-reader-*.tar.gz' -mtime +14 -delete
echo "$backup_dir/paper-reader-$timestamp.tar.gz"

