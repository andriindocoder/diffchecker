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

# Set PATH explicitly as a fallback
export JAVA_HOME=/usr/lib/jvm/java-11-amazon-corretto
export M2_HOME=/opt/maven
export PATH=$M2_HOME/bin:$JAVA_HOME/bin:$PATH

# Source .bashrc
. /root/.bashrc

# Start the SSH daemon
exec /usr/sbin/sshd -D