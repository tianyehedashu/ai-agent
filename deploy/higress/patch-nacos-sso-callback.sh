#!/bin/sh
set -e
NACOS="http://nacos-service.test.svc.cluster.local:8848"
AUTH="username=nacos&password=nacos"
TMP="/var/lib/istio/data/giikin-auth-fix.yml"

curl -sf "${NACOS}/nacos/v1/cs/configs?dataId=giikin-auth.yml&group=GIIKIN_IAM&tenant=test&${AUTH}" -o "$TMP"
sed -i 's|^    redirect-uri: https\?://gateway.giimallai.com/sso-callback|    redirect-uri:|' "$TMP"

curl -sf -X POST "${NACOS}/nacos/v1/cs/configs" \
  --data-urlencode "dataId=giikin-auth.yml" \
  --data-urlencode "group=GIIKIN_IAM" \
  --data-urlencode "tenant=test" \
  --data-urlencode "type=yaml" \
  --data-urlencode "content@${TMP}" \
  -d "${AUTH}"

echo "OK: redirect-uri cleared"
