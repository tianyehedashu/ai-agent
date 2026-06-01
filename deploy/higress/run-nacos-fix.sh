#!/bin/sh
B64=$(base64 -w0 /tmp/patch-nacos-sso-callback.sh)
kubectl -n test exec deploy/higress-gateway -- sh -c "echo $B64 | base64 -d | sh"
