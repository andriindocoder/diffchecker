#!/bin/bash

# Define the file path
POM_FILE="pom.xml"

# Backup the original pom.xml
cp "$POM_FILE" "${POM_FILE}.bak"

echo "Original pom.xml backed up."

# Dependencies to add
declare -a dependencies=(
    "<dependency>\n\t<groupId>org.springdoc</groupId>\n\t<artifactId>springdoc-openapi-ui</artifactId>\n\t<version>1.8.0</version>\n</dependency>"
    "<dependency>\n\t<groupId>com.h2database</groupId>\n\t<artifactId>h2</artifactId>\n</dependency>"
    "<dependency>\n\t<groupId>org.mockito</groupId>\n\t<artifactId>mockito-core</artifactId>\n\t<version>3.12.4</version>\n</dependency>"
    "<dependency>\n\t<groupId>org.springframework.cloud</groupId>\n\t<artifactId>spring-cloud-starter-aws-messaging</artifactId>\n</dependency>"
    "<dependency>\n\t<groupId>com.amazonaws</groupId>\n\t<artifactId>aws-java-sdk-sts</artifactId>\n</dependency>"
)

# Function to check if a dependency is already in the pom.xml
function dependency_exists {
    local groupId=$(echo "$1" | grep -o '<groupId>.*</groupId>' | sed 's/<\/\?groupId>//g')
    local artifactId=$(echo "$1" | grep -o '<artifactId>.*</artifactId>' | sed 's/<\/\?artifactId>//g')
    grep -q "<groupId>$groupId</groupId>.*<artifactId>$artifactId</artifactId>" "$POM_FILE"
}

# Use awk to add dependencies before the closing </dependencies> tag that is not part of dependencyManagement or build
for dependency in "${dependencies[@]}"; do
    if ! dependency_exists "$dependency"; then
        awk -v dep="$dependency" '
            /<\/dependencies>/ && !insideDependencyManagement && !insideBuild {print dep; print; next}
            {print}
            /<dependencyManagement>/ {insideDependencyManagement=1}
            /<\/dependencyManagement>/ {insideDependencyManagement=0}
            /<build>/ {insideBuild=1}
            /<\/build>/ {insideBuild=0}
        ' "$POM_FILE" > temp && mv temp "$POM_FILE"
    fi
done

echo "Dependencies added/updated successfully."

# Add <finalName> to <build> if not present
if ! grep -q "<finalName>" "$POM_FILE"; then
    awk '
        /<\/build>/ {
            print "    <finalName>app</finalName>"
            print
            next
        }
        {print}
    ' "$POM_FILE" > temp && mv temp "$POM_FILE"
    echo "<finalName> added successfully."
else
    echo "<finalName> already exists."
fi

# Profile to add
PROFILE="<profile>\n\t<id>cdx-pfm-cdx-pfm-devel</id>\n\t<activation>\n\t\t<activeByDefault>true</activeByDefault>\n\t</activation>\n\t<repositories>\n\t\t<repository>\n\t\t\t<id>cdx-pfm-cdx-pfm-devel</id>\n\t\t\t<url>https://cdx-pfm-482680362026.d.codeartifact.ap-southeast-1.amazonaws.com/maven/cdx-pfm-devel/</url>\n\t\t</repository>\n\t</repositories>\n</profile>"

# Check if the <profiles> section exists and add it if not
if ! grep -q "<profiles>" "$POM_FILE"; then
    awk -v profile="$PROFILE" '
        /<\/project>/ {
            print "<profiles>"
            print profile
            print "</profiles>"
            print
            next
        }
        {print}
    ' "$POM_FILE" > temp && mv temp "$POM_FILE"
    echo "<profiles> section added successfully."
else
    # Check if the profile already exists
    if ! grep -q "<id>cdx-pfm-cdx-pfm-devel</id>" "$POM_FILE"; then
        awk -v profile="$PROFILE" '
            /<\/profiles>/ {
                print profile
                print
                next
            }
            {print}
        ' "$POM_FILE" > temp && mv temp "$POM_FILE"
        echo "Profile added successfully."
    else
        echo "Profile already exists."
    fi
fi
