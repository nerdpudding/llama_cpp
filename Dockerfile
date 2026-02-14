# =============================================================================
# llama.cpp Docker build for RTX 4090 (sm_89) + RTX 5070 Ti (sm_120)
# CUDA 13.0 required for sm_120 support
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build
# ---------------------------------------------------------------------------
FROM nvidia/cuda:13.0.0-devel-ubuntu24.04 AS build

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        cmake \
        g++ \
        libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY llama.cpp/ .

RUN cmake -B build \
        -DGGML_CUDA=ON \
        -DCMAKE_CUDA_ARCHITECTURES="89;120" \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=OFF \
        -DCMAKE_EXE_LINKER_FLAGS="-L/usr/local/cuda/lib64/stubs" \
    && cmake --build build --target llama-server -j"$(nproc)"

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM nvidia/cuda:13.0.0-runtime-ubuntu24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libcurl4t64 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /build/build/bin/llama-server /usr/local/bin/llama-server

# ---------------------------------------------------------------------------
# Runtime configuration via environment variables
# ---------------------------------------------------------------------------
ENV MODEL=/models/model.gguf
ENV CTX_SIZE=131072
ENV N_GPU_LAYERS=99
ENV HOST=0.0.0.0
ENV PORT=8080
ENV SPLIT_MODE=layer
ENV TENSOR_SPLIT=
ENV MAIN_GPU=0
ENV FLASH_ATTN=1
ENV KV_CACHE_TYPE_K=q8_0
ENV KV_CACHE_TYPE_V=q8_0
ENV FIT=on
ENV FIT_TARGET=
ENV FIT_CTX=
ENV EXTRA_ARGS=

EXPOSE 8080

CMD set -e; \
    ARGS="--model ${MODEL}"; \
    ARGS="${ARGS} --ctx-size ${CTX_SIZE}"; \
    ARGS="${ARGS} --n-gpu-layers ${N_GPU_LAYERS}"; \
    ARGS="${ARGS} --host ${HOST}"; \
    ARGS="${ARGS} --port ${PORT}"; \
    ARGS="${ARGS} --split-mode ${SPLIT_MODE}"; \
    if [ -n "${TENSOR_SPLIT}" ]; then ARGS="${ARGS} --tensor-split ${TENSOR_SPLIT}"; fi; \
    ARGS="${ARGS} --main-gpu ${MAIN_GPU}"; \
    if [ "${FLASH_ATTN}" = "1" ]; then ARGS="${ARGS} --flash-attn on"; fi; \
    ARGS="${ARGS} --cache-type-k ${KV_CACHE_TYPE_K}"; \
    ARGS="${ARGS} --cache-type-v ${KV_CACHE_TYPE_V}"; \
    ARGS="${ARGS} --fit ${FIT}"; \
    if [ -n "${FIT_TARGET}" ]; then ARGS="${ARGS} --fit-target ${FIT_TARGET}"; fi; \
    if [ -n "${FIT_CTX}" ]; then ARGS="${ARGS} --fit-ctx ${FIT_CTX}"; fi; \
    if [ -n "${EXTRA_ARGS}" ]; then ARGS="${ARGS} ${EXTRA_ARGS}"; fi; \
    echo "Starting llama-server with: ${ARGS}"; \
    exec llama-server ${ARGS}
