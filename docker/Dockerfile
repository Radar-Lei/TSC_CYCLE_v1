FROM unsloth/unsloth:dgxspark-latest

USER root

ENV DEBIAN_FRONTEND=noninteractive \
    SUMO_HOME=/usr/share/sumo \
    TZ=Asia/Shanghai

RUN apt-get update -o Acquire::Retries=5 && \
    apt-get install -o Acquire::Retries=5 -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
        tzdata \
        software-properties-common && \
    rm -rf /var/lib/apt/lists/*

RUN add-apt-repository ppa:sumo/stable -y && \
    apt-get update -o Acquire::Retries=5 && \
    apt-get install -o Acquire::Retries=5 -y --no-install-recommends \
        sumo sumo-tools sumo-doc \
        mesa-utils libgl1-mesa-dri libglx-mesa0 libglu1-mesa \
        fluxbox x11-utils x11vnc xvfb && \
    rm -rf /var/lib/apt/lists/*

RUN pip install traci modelscope scikit-learn --break-system-packages

# 创建与宿主机用户匹配的用户（UID和GID通过ARG传递）
# 默认使用1000:1000，与常见的Linux用户匹配
ARG USER_ID=1000
ARG GROUP_ID=1000

# 删除可能存在的冲突用户和组，然后创建新的
RUN if id ${USER_ID} >/dev/null 2>&1; then \
      USERNAME=$(id -nu ${USER_ID}); \
      userdel -r ${USERNAME} 2>/dev/null || true; \
    fi && \
    if getent group ${GROUP_ID}; then \
      GROUPNAME=$(getent group ${GROUP_ID} | cut -d: -f1); \
      groupdel ${GROUPNAME} 2>/dev/null || true; \
    fi && \
    groupadd -g ${GROUP_ID} samuel && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash samuel && \
    usermod -aG sudo samuel && \
    echo 'samuel ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# 创建工作目录并设置权限
RUN mkdir -p /home/samuel/SCU_TSC && \
    chown -R samuel:samuel /home/samuel/SCU_TSC

# 切换到非root用户
USER samuel
WORKDIR /home/samuel/SCU_TSC

# 正确设置PATH - 系统路径优先，然后是SUMO
ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/share/sumo/bin:/usr/local/cuda/bin"
