# Dockerfile

#ARG PROXY_ADDR="http://host.docker.internal:7890" Linxux 下使用 host.docker.internal 可能会有问题，建议使用实际的代理地址
FROM node:20-bookworm-slim AS frontend-builder

ARG DEBIAN_FRONTEND=noninteractive
ARG PROXY_ADDR

ENV HTTP_PROXY=${PROXY_ADDR}
ENV HTTPS_PROXY=${PROXY_ADDR}

WORKDIR /app/static/frontend
COPY static/frontend/package.json static/frontend/package-lock.json ./
RUN npm ci

COPY static/frontend ./
RUN npm run build

FROM python:3.10-slim-bookworm AS builder

ARG DEBIAN_FRONTEND=noninteractive
ARG PROXY_ADDR

RUN if [ -n "$PROXY_ADDR" ]; then \
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' "$PROXY_ADDR" "$PROXY_ADDR" > /etc/apt/apt.conf.d/99proxy; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    if [ -n "$PROXY_ADDR" ]; then rm -f /etc/apt/apt.conf.d/99proxy; fi

ENV HTTP_PROXY=${PROXY_ADDR}
ENV HTTPS_PROXY=${PROXY_ADDR}

ENV POETRY_HOME="/opt/poetry"
ENV POETRY_VERSION=1.8.3
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION}
ENV PATH="${POETRY_HOME}/bin:${PATH}"

WORKDIR /app_builder
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false --local && \
    poetry install --no-root --no-dev --no-interaction --no-ansi

FROM python:3.10-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive
ARG PROXY_ADDR

ENV HTTP_PROXY=${PROXY_ADDR}
ENV HTTPS_PROXY=${PROXY_ADDR}

# 步骤 1: 安装所有系统依赖。
# Playwright 的依赖也在这里一并安装。
RUN \
    if [ -n "$PROXY_ADDR" ]; then \
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' "$PROXY_ADDR" "$PROXY_ADDR" > /etc/apt/apt.conf.d/99proxy; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libxrender1 libxtst6 ca-certificates fonts-liberation libasound2 libpangocairo-1.0-0 libpango-1.0-0 libu2f-udev \
    supervisor curl \
    && \
    # 清理工作
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    if [ -n "$PROXY_ADDR" ]; then rm -f /etc/apt/apt.conf.d/99proxy; fi

RUN groupadd -r appgroup && useradd -r -g appgroup -s /bin/bash -d /app appuser

WORKDIR /app

# 步骤 2: 复制 Python 包和可执行文件。
# 这是关键的顺序调整：在使用 playwright 之前先把它复制进来。
COPY --from=builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /opt/poetry/bin/poetry /usr/local/bin/poetry

# 复制应用代码
COPY . .
COPY --from=frontend-builder /app/static/frontend/dist /app/static/frontend/dist

# 步骤 3: 现在 Python 模块已存在，可以安全地运行这些命令。
# 注意：我们不再需要 `playwright install-deps`，因为依赖已在上面的 apt-get 中安装。
RUN camoufox fetch && \
    python -m playwright install firefox

# 创建目录和设置权限
RUN mkdir -p /app/logs && \
    mkdir -p /app/auth_profiles/active && \
    mkdir -p /app/auth_profiles/saved && \
    mkdir -p /app/certs && \
    mkdir -p /app/browser_utils/custom_scripts && \
    mkdir -p /home/appuser/.cache/ms-playwright && \
    mkdir -p /home/appuser/.mozilla && \
    chown -R appuser:appgroup /app && \
    chown -R appuser:appgroup /home/appuser

COPY supervisord.conf /etc/supervisor/conf.d/app.conf

# 修复 camoufox 缓存逻辑
RUN mkdir -p /var/cache/camoufox && \
    if [ -d /root/.cache/camoufox ]; then cp -a /root/.cache/camoufox/* /var/cache/camoufox/; fi && \
    mkdir -p /app/.cache && \
    ln -s /var/cache/camoufox /app/.cache/camoufox

# 1. 以 root 身份创建目录并提前授权给 appuser
# 这样即使构建阶段下载失败，容器启动后 appuser 也有权限自己下载
RUN mkdir -p /usr/local/lib/python3.10/site-packages/browserforge/headers/data && \
    mkdir -p /usr/local/lib/python3.10/site-packages/browserforge/fingerprints/data && \
    chown -R appuser:appgroup /usr/local/lib/python3.10/site-packages/browserforge

# 2. 尝试在构建阶段下载数据 (加上 || true 保证即使网络波动也不报错中断构建)
# 我们在前面已经设置了 ENV HTTP_PROXY，这里会尝试使用代理
RUN python3 -m browserforge.headers update || echo "Warning: Headers download failed during build."
RUN python3 -m browserforge.fingerprints update || echo "Warning: Fingerprints download failed during build."

# 3. 运行你自己的脚本 (同样加上容错)
RUN python scripts/update_browserforge_data.py || echo "Warning: Custom update script failed."

# 4. 再次确保权限正确（防止脚本创建了新文件导致权限回归 root）
RUN chown -R appuser:appgroup /usr/local/lib/python3.10/site-packages/browserforge

# 清理代理环境变量
ENV HTTP_PROXY=""
ENV HTTPS_PROXY=""

EXPOSE 2048
EXPOSE 3120

USER appuser
ENV HOME=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

ENV PYTHONUNBUFFERED=1

ENV PORT=8000
ENV DEFAULT_FASTAPI_PORT=2048
ENV DEFAULT_CAMOUFOX_PORT=9222
ENV STREAM_PORT=3120
ENV SERVER_LOG_LEVEL=INFO
ENV DEBUG_LOGS_ENABLED=false
ENV AUTO_CONFIRM_LOGIN=true
ENV SERVER_PORT=2048
ENV INTERNAL_CAMOUFOX_PROXY=""

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/app.conf"]
