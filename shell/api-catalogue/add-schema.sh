#!/bin/bash

# Define the schema.sql file path
SCHEMA_FILE="src/main/resources/schema.sql"

# Create the schema.sql file with the given content
cat <<EOL > $SCHEMA_FILE
CREATE TABLE crons (
  id VARCHAR(255) PRIMARY KEY,
  name VARCHAR(255),
  value VARCHAR(255),
  created_by VARCHAR(255),
  created_at TIMESTAMP,
  updated_by VARCHAR(255),
  updated_at TIMESTAMP,
  deleted_by VARCHAR(255),
  deleted_at TIMESTAMP,
  version INTEGER
);

CREATE TABLE event_subscriber (
  id VARCHAR(255) PRIMARY KEY,
  description TEXT,
  event_types TEXT,
  owning_application VARCHAR(255),
  created_by VARCHAR(255),
  created_at TIMESTAMP,
  updated_by VARCHAR(255),
  updated_at TIMESTAMP,
  deleted_by VARCHAR(255),
  deleted_at TIMESTAMP,
  version INTEGER
);
EOL

echo "schema.sql has been updated with the specified content."
