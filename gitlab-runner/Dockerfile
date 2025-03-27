FROM debian:buster

# ---------------------------------------------------------------------
# Install tini (AMD64 version for ECS x86_64 compatibility)
# ---------------------------------------------------------------------
ARG TINI_VERSION=v0.19.0

RUN apt-get update && \
    apt-get install -y curl && \
    curl -Lo /usr/local/bin/tini https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-amd64 && \
    chmod +x /usr/local/bin/tini

# --------------------------------------------------------------------------
# Install and configure sshd
# --------------------------------------------------------------------------
RUN apt-get install -y openssh-server && \
    mkdir -p /run/sshd

EXPOSE 22

# ----------------------------------------
# Install GitLab CI dependencies (AMD64 version)
# ----------------------------------------
ARG GITLAB_RUNNER_VERSION=v12.9.0

RUN curl -Lo /usr/local/bin/gitlab-runner https://gitlab-runner-downloads.s3.amazonaws.com/${GITLAB_RUNNER_VERSION}/binaries/gitlab-runner-linux-amd64 && \
    chmod +x /usr/local/bin/gitlab-runner && \
    gitlab-runner --version

RUN apt-get install -y bash ca-certificates git git-lfs && \
    git lfs install --skip-repo

# Install required packages and Corretto 11 JDK
RUN apt-get update && \
    apt-get install -y wget gnupg2 software-properties-common && \
    wget -O- https://apt.corretto.aws/corretto.key | apt-key add - && \
    add-apt-repository 'deb https://apt.corretto.aws stable main' && \
    apt-get update && \
    apt-get install -y java-11-amazon-corretto-jdk && \
    apt-get clean

# Install Maven manually (version 3.9.6)
ENV MAVEN_VERSION=3.9.6
RUN wget https://downloads.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz && \
    tar xzf apache-maven-${MAVEN_VERSION}-bin.tar.gz -C /opt && \
    ln -s /opt/apache-maven-${MAVEN_VERSION} /opt/maven && \
    rm apache-maven-${MAVEN_VERSION}-bin.tar.gz

# Install AWS CLI v2
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    apt-get install -y unzip && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -f awscliv2.zip && \
    rm -rf aws

# ----------------------------------------
# Install Docker
# ----------------------------------------
RUN apt-get update && \
    apt-get install -y apt-transport-https ca-certificates curl && \
    apt-get install -y docker.io && \
    apt-get clean

# Set environment variables in .bashrc for SSH sessions
RUN echo "export JAVA_HOME=/usr/lib/jvm/java-11-amazon-corretto" >> /root/.bashrc && \
    echo "export M2_HOME=/opt/maven" >> /root/.bashrc && \
    echo "export PATH=\$M2_HOME/bin:\$JAVA_HOME/bin:\$PATH" >> /root/.bashrc

# Add default settings.xml (optional, adjust as needed)
RUN mkdir -p /root/.m2
COPY settings.xml /root/.m2/settings.xml

# -------------------------------------------------------------------------------------
# Copy and set up the entrypoint script
# -------------------------------------------------------------------------------------
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
