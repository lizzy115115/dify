#!/usr/bin/env bash
# Fast pre-pull: reuse local Dify images; Milvus via domestic full mirrors (Huawei SWR first).
set -uo pipefail
cd "$(dirname "$0")"

ARCH="$(uname -m)"
QUAY_MIRRORS=(quay.m.daocloud.io)

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
has() { docker image inspect "$1" >/dev/null 2>&1; }

reuse_local() {
  local target="$1" source="$2"
  if has "$target"; then log "SKIP $target"; return 0; fi
  if has "$source"; then
    docker tag "$source" "$target"
    log "REUSE $source -> $target"
    return 0
  fi
  return 1
}

# Reuse already-downloaded Dify images (skip ~1.7GB download)
reuse_local "langgenius/dify-api:1.15.0" "langgenius/dify-api:1.14.2"
reuse_local "langgenius/dify-web:1.15.0" "langgenius/dify-web:1.14.2"
reuse_local "langgenius/dify-plugin-daemon:0.6.3-local" "langgenius/dify-plugin-daemon:0.6.1-local"

pull_docker_io() {
  local target="$1"
  has "$target" && { log "SKIP $target"; return 0; }
  local mirrors=(
    docker.1ms.run
    docker.awsl9527.cn
    docker.m.daocloud.io
    docker.kejilion.pro
  )
  for m in "${mirrors[@]}"; do
    log "pull ${m}/${target}"
    if docker pull "${m}/${target}"; then
      docker tag "${m}/${target}" "${target}"
      return 0
    fi
  done
  log "pull direct ${target}"
  docker pull "$target"
}

pull_milvus_v263() {
  local target="milvusdb/milvus:v2.6.3"
  has "$target" && { log "SKIP ${target}"; return 0; }

  # Huawei Cloud SWR: domestic full copy, fastest for CN (see docker.aityp.com)
  local hw_base="swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/milvusdb/milvus"
  local hw_candidates=()
  if [[ "$ARCH" == "arm64" || "$ARCH" == "aarch64" ]]; then
    hw_candidates+=("${hw_base}:v2.6.3-linuxarm64")
  fi
  hw_candidates+=("${hw_base}:v2.6.3")

  local candidates=(
    "${hw_candidates[@]}"
    "docker.1ms.run/milvusdb/milvus:v2.6.3"
    "docker.awsl9527.cn/milvusdb/milvus:v2.6.3"
    "docker.m.daocloud.io/milvusdb/milvus:v2.6.3"
    "docker.kejilion.pro/milvusdb/milvus:v2.6.3"
  )

  for src in "${candidates[@]}"; do
    log "pull ${src}"
    if docker pull "${src}"; then
      docker tag "${src}" "${target}"
      log "OK ${target} <- ${src}"
      return 0
    fi
    log "FAIL ${src}, try next..."
  done

  log "pull direct ${target}"
  docker pull "${target}"
}

pull_quay_io() {
  local target="$1" path="${1#quay.io/}"
  has "$target" && return 0
  for m in "${QUAY_MIRRORS[@]}"; do
    docker pull "${m}/${path}" && docker tag "${m}/${path}" "$target" && return 0
  done
  docker pull "$target"
}

log "=== infra (skip if exists) ==="
for img in \
  "langgenius/dify-sandbox:0.2.15" \
  "postgres:15-alpine" "redis:6-alpine" \
  "nginx:latest" "ubuntu/squid:latest" "busybox:latest" \
  "minio/minio:RELEASE.2023-03-20T20-16-18Z"; do
  pull_docker_io "$img" &
done
wait

pull_quay_io "quay.io/coreos/etcd:v3.5.5"

log "=== milvus v2.6.3 (arch=${ARCH}, Huawei SWR first) ==="
pull_milvus_v263

log "=== done ==="
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' \
  | grep -E 'REPOSITORY|milvus:v2.6|dify-api:1.15|dify-web:1.15|plugin-daemon:0.6.3'
log "Run: docker compose up -d"
