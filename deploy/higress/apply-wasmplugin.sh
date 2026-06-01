#!/bin/sh
set -e
NS=test
kubectl -n $NS patch mcpbridge default --type=json --patch-file=/tmp/mcpbridge-iam-redis.patch.json 2>/dev/null || true
REDIS_PASS=$(kubectl -n $NS get secret ai-agent-backend-env -o jsonpath='{.data.REDIS_PASSWORD}' | base64 -d)
sed "s/REPLACE_WITH_IAM_REDIS_PASSWORD/${REDIS_PASS}/g" /tmp/giikin-auth-bridge-wasmplugin.yaml | kubectl -n $NS apply -f -
kubectl -n $NS get wasmplugin giikin-auth-bridge-ai-agent -o wide 2>/dev/null || true
