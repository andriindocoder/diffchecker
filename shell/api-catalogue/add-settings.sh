#!/bin/bash

# Define the file path
SETTINGS_FILE="settings.xml"

# Function to create settings.xml with the expected content
create_settings_xml() {
    cat <<EOF > "$SETTINGS_FILE"
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 https://maven.apache.org/xsd/settings-1.0.0.xsd">
    <servers>
      <server>
        <id>cdx-pfm-cdx-pfm-devel</id>
        <username>aws</username>
        <password>\${env.CODEARTIFACT_AUTH_TOKEN}</password>
      </server>
    </servers>
</settings>
EOF
    echo "settings.xml created successfully."
}

# Check if the settings.xml file exists
if [ -f "$SETTINGS_FILE" ]; then
    echo "settings.xml already exists. No changes made."
else
    create_settings_xml
fi
