#!/bin/sh
# 在 wuhan-ali 上执行：部署 giikin-auth-bridge + 修复 IAM SSO 回调
set -e
NS=test
WASM=/tmp/plugin.wasm
REDIS_PASS="${REDIS_PASS:-$(kubectl -n $NS get secret ai-agent-backend-env -o jsonpath='{.data.REDIS_PASSWORD}' | base64 -d)}"

echo "==> 1. Split wasm into 900KB secrets (K8s limit 1MB/value)"
kubectl -n $NS delete secret giikin-auth-bridge-wasm-00 giikin-auth-bridge-wasm-01 giikin-auth-bridge-wasm-02 giikin-auth-bridge-wasm-03 giikin-auth-bridge-wasm-04 giikin-auth-bridge-wasm-05 giikin-auth-bridge-wasm-06 --ignore-not-found
rm -f /tmp/plugin.wasm.part*
split -b 900000 -d -a 2 "$WASM" /tmp/plugin.wasm.part
PART_COUNT=0
for f in /tmp/plugin.wasm.part*; do
  [ -f "$f" ] || continue
  idx=$(basename "$f" | sed 's/plugin.wasm.part//')
  kubectl -n $NS delete secret "giikin-auth-bridge-wasm-${idx}" --ignore-not-found
  kubectl -n $NS create secret generic "giikin-auth-bridge-wasm-${idx}" --from-file=part="$f"
  PART_COUNT=$((PART_COUNT + 1))
done
echo "Created $PART_COUNT wasm part secrets"

echo "==> 2. Push OCI image via Kaniko Job"
kubectl -n $NS delete job push-giikin-auth-bridge-wasm --ignore-not-found
kubectl -n $NS apply -f /tmp/push-giikin-auth-bridge-job.yaml
kubectl -n $NS wait --for=condition=complete job/push-giikin-auth-bridge-wasm --timeout=300s

echo "==> 3. Register IAM Redis in McpBridge"
if ! kubectl -n $NS get mcpbridge default -o yaml | grep -q iam-session-redis; then
  kubectl -n $NS patch mcpbridge default --type=json --patch-file=/tmp/mcpbridge-iam-redis.patch.json
fi

echo "==> 4. Apply WasmPlugin"
sed "s/REPLACE_WITH_IAM_REDIS_PASSWORD/${REDIS_PASS}/g" /tmp/giikin-auth-bridge-wasmplugin.yaml | kubectl -n $NS apply -f -

echo "==> 5. Patch Nacos company.sso.redirect-uri (enable callbackOrigin)"
GW_POD=$(kubectl -n $NS get pod -l app=higress-gateway -o jsonpath='{.items[0].metadata.name}')
kubectl -n $NS cp /tmp/patch-nacos-sso-callback.sh "$GW_POD:/tmp/patch-nacos-sso-callback.sh"
kubectl -n $NS exec "$GW_POD" -- sh /tmp/patch-nacos-sso-callback.sh

echo "==> 6. Verify binding redirect contains /ai-agent/sso-callback"
curl -sf "http://gateway.giimallai.com/api/auth/binding/company_sso?tenantId=000000&domain=admin&callbackOrigin=http://gateway.giimallai.com/ai-agent" | grep -o '/ai-agent/sso-callback' && echo " OK" || echo " WARN: callback not fixed yet"

echo "DONE"
