#!/bin/bash
# 构建 AI Agent 沙箱镜像

set -e

IMAGE_NAME="ai-agent-sandbox"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE="${SCRIPT_DIR}/Dockerfile"

echo "Building ${FULL_IMAGE}..."
echo "Dockerfile: ${DOCKERFILE}"

cd "${SCRIPT_DIR}"

docker build \
    -t "${FULL_IMAGE}" \
    -f "${DOCKERFILE}" \
    .

echo ""
echo "✅ Build complete!"
echo "   Image: ${FULL_IMAGE}"
echo ""
echo "To test:"
echo "   docker run -it --rm ${FULL_IMAGE} bash"
echo ""
echo "To push (if needed):"
echo "   docker tag ${FULL_IMAGE} <registry>/${FULL_IMAGE}"
echo "   docker push <registry>/${FULL_IMAGE}"
