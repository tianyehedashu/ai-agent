#!/bin/sh
# 在 VPC 内、已 docker login ACR 的机器上执行
set -e
IMAGE=giimall-acr-registry-vpc.cn-hangzhou.cr.aliyuncs.com/prod/giikin-auth-bridge:1.0.0
BUILD=/tmp/giikin-wasm-build
WASM=/tmp/plugin.wasm
[ -f "$WASM" ] || { echo "missing $WASM"; exit 1; }
rm -rf "$BUILD"
mkdir -p "$BUILD"
cp "$WASM" "$BUILD/plugin.wasm"
printf 'FROM scratch\nCOPY plugin.wasm plugin.wasm\n' > "$BUILD/Dockerfile"
docker build -t "$IMAGE" "$BUILD"
docker push "$IMAGE"
echo "Pushed $IMAGE"
