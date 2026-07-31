#!/bin/bash

# Script to create the directory structure for ave_forensics
# Run this from the parent directory of ave_forensics

set -e  # Exit on error

BASE_DIR="ave_forensics"

echo "Creating directory structure under $BASE_DIR..."

# Create all directories
mkdir -p $BASE_DIR/device_forensics/methodology
mkdir -p $BASE_DIR/device_forensics/specimens/lumenate_nova/{original,hashes,metadata,versions}
mkdir -p $BASE_DIR/device_forensics/static/lumenate_nova/{jadx,apktool,apkanalyzer,mobsf,native,findings}
mkdir -p $BASE_DIR/device_forensics/dynamic/lumenate_nova/{adb,frida,network,bluetooth,filesystem,findings}
mkdir -p $BASE_DIR/device_forensics/protocol_reconstruction/lumenate_nova/{session_catalog,timing_models,light_sequences,transport_protocol,state_machine,hypotheses}
mkdir -p $BASE_DIR/device_forensics/physical_validation/lumenate_nova/{photodiode,oscilloscope,camera,synchronization,comparisons}
mkdir -p $BASE_DIR/device_forensics/tools
mkdir -p $BASE_DIR/device_forensics/reports/lumenate_nova

# Create files
touch $BASE_DIR/device_forensics/README.md
touch $BASE_DIR/device_forensics/methodology/{scope.md,evidence_model.md,confidence_levels.md,legal_and_safety_boundaries.md}

echo "Directory structure created successfully!"

# Optional: list the tree if tree command is available
if command -v tree >/dev/null 2>&1; then
    echo "Verifying structure:"
    tree $BASE_DIR
else
    echo "Tree command not available. Structure created."
fi
