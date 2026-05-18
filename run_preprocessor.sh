#!/bin/bash

# Default configuration file
CONFIG_FILE=${1:-"tools/PreProcessor/config/test_config.json"}

# 1. Run surface_resampler (if compiled)
if [ -f "build/surface_resampler" ]; then
    echo "Running surface_resampler with config: $CONFIG_FILE"
    ./build/surface_resampler "$CONFIG_FILE"
    
    # 2. Run visualization script
    # Note: The result file name might vary based on config, 
    # but we'll check for the common output location.
    RESULT_FILE="Results/circle_resampled.dat"
    if [ -f "$RESULT_FILE" ]; then
        echo "Launching visualization: $RESULT_FILE..."
        python3 tools/scripts/visualize_dat.py "$RESULT_FILE"
    else
        echo "Warning: Output file $RESULT_FILE not found. Cannot visualize."
    fi
else
    echo "Error: build/surface_resampler not found. Please run ./build.sh first."
fi
