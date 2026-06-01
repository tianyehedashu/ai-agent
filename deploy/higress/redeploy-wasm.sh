#!/bin/sh
set -e
NS=test
WASM=/tmp/plugin.wasm

echo "==> wasm file"
ls -lh "$WASM"

echo "==> split wasm into secrets"
kubectl -n "$NS" delete secret \
  giikin-auth-bridge-wasm-00 giikin-auth-bridge-wasm-01 giikin-auth-bridge-wasm-02 \
  giikin-auth-bridge-wasm-03 giikin-auth-bridge-wasm-04 giikin-auth-bridge-wasm-05 \
  giikin-auth-bridge-wasm-06 --ignore-not-found
rm -f /tmp/plugin.wasm.part*
split -b 900000 -d -a 2 "$WASM" /tmp/plugin.wasm.part
for f in /tmp/plugin.wasm.part*; do
  idx=$(basename "$f" | sed 's/plugin.wasm.part//')
  kubectl -n "$NS" create secret generic "giikin-auth-bridge-wasm-${idx}" --from-file=part="$f"
done

echo "==> push oci to ttl.sh"
kubectl -n "$NS" delete job push-giikin-auth-bridge-wasm --ignore-not-found --wait=true
kubectl -n "$NS" replace -f /tmp/push-giikin-auth-bridge-job.yaml --force
kubectl -n "$NS" wait --for=condition=complete job/push-giikin-auth-bridge-wasm --timeout=180s
kubectl -n "$NS" logs -l job-name=push-giikin-auth-bridge-wasm -c push-oci --tail=5

echo "==> apply WasmPlugin"
sh /tmp/apply-wasmplugin.sh

echo "==> restart higress-gateway"
kubectl -n "$NS" rollout restart deploy/higress-gateway
kubectl -n "$NS" rollout status deploy/higress-gateway --timeout=120s

echo "==> verify wasm load"
kubectl -n "$NS" logs deploy/higress-gateway --tail=30 | grep -iE 'giikin|wasm|error' || true

echo "DONE"
