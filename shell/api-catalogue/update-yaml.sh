#!/bin/bash

# Define the paths to your YAML files
YAML_FILE="src/main/resources/application-local.yaml"
YML_FILE="src/main/resources/application-local.yml"

# Determine which file exists
if [ -f "$YAML_FILE" ]; then
    FILE_TO_UPDATE="$YAML_FILE"
elif [ -f "$YML_FILE" ]; then
    FILE_TO_UPDATE="$YML_FILE"
else
    echo "Neither application-local.yaml nor application-local.yml was found."
    exit 1
fi

# Create a temporary backup of the original YAML file
cp "$FILE_TO_UPDATE" "${FILE_TO_UPDATE}.bak"

# Remove the existing spring, server.port, and springdoc content in the YAML file, but keep other parts intact
awk '/^spring:/ {flag_spring=1; next} /^server:/ {flag_server=1; next} /^springdoc:/ {flag_springdoc=1; next} /^[^ ]/ {flag_spring=0; flag_server=0; flag_springdoc=0} !flag_spring && !flag_server && !flag_springdoc {print}' "$FILE_TO_UPDATE" > temp.yaml

# Write the new spring content to the temporary file
cat <<'EOF' >> temp.yaml
spring:
  main:
    lazy-initialization: false
  jpa:
    hibernate:
      ddl-auto: none
    show-sql: false
  datasource:
    url: jdbc:h2:mem:testdb
    driverClassName: org.h2.Driver
    username: sa
    password: password
  flyway:
    enabled: false
  h2:
    console:
      enabled: true
      path: /h2-console

server:
  port: 8080

springdoc:
  api-docs:
    groups:
      enabled: true
    path: /internal/swagger-doc/v3/api-docs
  swagger-ui:
    path: /internal/swagger-doc/swagger-ui.html
EOF

# Move the temp file to the original file
mv temp.yaml "$FILE_TO_UPDATE"

# Print a message indicating that the script has finished the update
echo "$FILE_TO_UPDATE has been updated."
