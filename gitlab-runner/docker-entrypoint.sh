#!/bin/bash

# Create a folder to store user's SSH keys if it does not exist
USER_SSH_KEYS_FOLDER=/root/.ssh
[ ! -d "$USER_SSH_KEYS_FOLDER" ] && mkdir -p "$USER_SSH_KEYS_FOLDER" && chmod 700 "$USER_SSH_KEYS_FOLDER"

# Copy contents from the SSH_PUBLIC_KEY environment variable to authorized_keys
if [ -z "$SSH_PUBLIC_KEY" ]; then
  echo "Error: SSH_PUBLIC_KEY environment variable is not set" >&2
  exit 1
fi
echo "$SSH_PUBLIC_KEY" > "$USER_SSH_KEYS_FOLDER/authorized_keys"
chmod 600 "$USER_SSH_KEYS_FOLDER/authorized_keys"

# Clear the SSH_PUBLIC_KEY environment variable
unset SSH_PUBLIC_KEY

# Set PATH explicitly, including /usr/bin for docker
export JAVA_HOME=/usr/lib/jvm/java-11-amazon-corretto
export M2_HOME=/opt/maven
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$M2_HOME/bin:$JAVA_HOME/bin:$PATH

# Source .bashrc (optional, for consistency)
. /root/.bashrc

# Run the provided command (e.g., for local testing) or start sshd
if [ $# -eq 0 ]; then
  exec /usr/sbin/sshd -D
else
  exec "$@"
fi