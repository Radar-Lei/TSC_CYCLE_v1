# TSC_CYCLE Benchmark Dockerfile
# Lightweight image with SUMO and Python for running traffic signal benchmarks

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    SUMO_HOME=/usr/share/sumo \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# Install system dependencies and SUMO
RUN apt-get update -o Acquire::Retries=5 && \
    apt-get install -o Acquire::Retries=5 -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
        tzdata \
        python3 \
        python3-pip \
        python3-venv \
        software-properties-common \
        gosu && \
    add-apt-repository ppa:sumo/stable -y && \
    apt-get update -o Acquire::Retries=5 && \
    apt-get install -o Acquire::Retries=5 -y --no-install-recommends \
        sumo sumo-tools sumo-doc \
        mesa-utils libgl1-mesa-dri libglx-mesa0 libglu1-mesa \
        fluxbox x11-utils x11vnc xvfb && \
    rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /srv/client

# Create virtual environment and install Python dependencies
RUN python3 -m venv /srv/client/.venv
ENV PATH="/srv/client/.venv/bin:$PATH"

# Install Python packages (traci comes from SUMO apt package)
# Use Tsinghua mirror for faster and more reliable downloads in China
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    openai \
    loguru \
    pydantic

# Create data directories
RUN mkdir -p /srv/sumo-data/logs /srv/sumo-data/runs /srv/sumo-data/config

# Copy entrypoint
COPY benchmark/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set environment
ENV PYTHONPATH=/srv/client:/usr/share/sumo/tools \
    SUMO_CONFIG_FILE=/srv/client/config/osm.sumocfg \
    SUMO_GUI=0 \
    SUMO_STEP_LENGTH=1.0 \
    SUMO_WARMUP_STEPS=300 \
    SUMO_CLIENT_BASE_DIR=/srv/sumo-data \
    SUMO_CLIENT_LOGS_DIR=/srv/sumo-data/logs

EXPOSE 8013
EXPOSE 5900

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
