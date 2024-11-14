#!/bin/bash

# Base directory containing the Java files
BASE_DIR="src/main/java"

# Find the main Spring Boot application class file
MAIN_CLASS_FILE=$(grep -rl "@SpringBootApplication" "$BASE_DIR")

# Check if the main class file was found
if [ -z "$MAIN_CLASS_FILE" ]; then
    echo "No Spring Boot application class found."
    exit 1
fi

# Extract the class name from the file name
MAIN_CLASS_NAME=$(basename "$MAIN_CLASS_FILE" .java)
echo "Main class file: $MAIN_CLASS_FILE";
echo "Main class name: $MAIN_CLASS_NAME";

# Create a temporary file
TEMP_FILE=$(mktemp)

# Use awk to modify the file content, ensuring that only the class name is changed in the class definition and not in SpringApplication.run
awk -v old_class_name="$MAIN_CLASS_NAME" '
    BEGIN { exclAdded=0 }
    /@SpringBootApplication/ && exclAdded == 0 {
        print "@SpringBootApplication(exclude = { MessagingAutoConfiguration.class })";
        exclAdded=1;
        next
    }
    # Replace the class name only in the class definition line
    /^public class / {
        gsub(old_class_name, "ApiInventorySpringdocApplication")
    }
    # Print the original SpringApplication.run line without modification
    /SpringApplication.run/ {
        print "SpringApplication.run(ApiInventorySpringdocApplication.class, args);"
        next
    }
    { print }
' "$MAIN_CLASS_FILE" > "$TEMP_FILE"

# Ensure the necessary import is included
if ! grep -q "org.springframework.cloud.aws.autoconfigure.messaging.MessagingAutoConfiguration" "$TEMP_FILE"; then
    awk '
        /import org.springframework.boot.autoconfigure.SpringBootApplication;/ {
            print;
            print "import org.springframework.cloud.aws.autoconfigure.messaging.MessagingAutoConfiguration;";
            next
        }
        { print }
    ' "$TEMP_FILE" > "${MAIN_CLASS_FILE%/*}/ApiInventorySpringdocApplication.java"
else
    mv "$TEMP_FILE" "${MAIN_CLASS_FILE%/*}/ApiInventorySpringdocApplication.java"
fi

# Remove temporary file if it still exists
[ -f "$TEMP_FILE" ] && rm "$TEMP_FILE"

# Remove the old file if the new file is created successfully
if [ -f "${MAIN_CLASS_FILE%/*}/ApiInventorySpringdocApplication.java" ]; then
    rm "$MAIN_CLASS_FILE"
    echo "File renamed and modified successfully."
else
    echo "Failed to create the new file."
fi

# Find the AWSConfig.java file
AWS_CONFIG_FILE=$(find "$BASE_DIR" -name "AWSConfig.java")

# Function to create AWSConfig.java with the expected content
create_aws_config() {
    echo "Creating AWSConfig.java file."
    PACKAGE_DIR=$(dirname "$1")
    PACKAGE_NAME=$(echo "$PACKAGE_DIR" | sed "s|$BASE_DIR/||" | tr '/' '.')
    cat <<EOF > "$1"
package $PACKAGE_NAME;

import co.reldyn.cdxcommonutil.config.AwsDevConfig;
import com.amazonaws.services.sqs.AmazonSQSAsync;
import org.mockito.Mockito;
import org.springframework.cloud.aws.messaging.core.QueueMessagingTemplate;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;

@Configuration
@Import({ AwsDevConfig.class })
public class AWSConfig {

    @Bean
    public AmazonSQSAsync amazonSQSAsync() {
        return Mockito.mock(AmazonSQSAsync.class);
    }

    @Bean
    public QueueMessagingTemplate queueMessagingTemplate(AmazonSQSAsync amazonSQSAsync) {
        return new QueueMessagingTemplate(amazonSQSAsync);
    }
}
EOF
}

# Check if the AWSConfig.java file was found
if [ -n "$AWS_CONFIG_FILE" ]; then
    echo "AWSConfig.java file found. Deleting and replacing with the expected content."
    rm "$AWS_CONFIG_FILE"
    create_aws_config "$AWS_CONFIG_FILE"
else
    # Find the configs directory
    CONFIGS_DIR=$(find "$BASE_DIR" -type d -name "configs" | head -n 1)

    if [ -n "$CONFIGS_DIR" ]; then
        AWS_CONFIG_FILE="$CONFIGS_DIR/AWSConfig.java"
        create_aws_config "$AWS_CONFIG_FILE"
    else
        echo "Configs directory not found. Creating the AWSConfig.java file in the base directory."
        DEFAULT_DIR=$(find "$BASE_DIR" -type d | head -n 1)
        AWS_CONFIG_FILE="$DEFAULT_DIR/AWSConfig.java"
        create_aws_config "$AWS_CONFIG_FILE"
    fi
fi

echo "AWSConfig.java file created/updated successfully."
