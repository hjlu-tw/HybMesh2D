#!/bin/bash

# Default configuration file
CONFIG_FILE=${1:-"tools/PreProcessor/config/test_curve_config.json"}

# 1. Run surface_resampler (if compiled)
if [ -f "build/surface_resampler" ]; then
    echo "Running surface_resampler with config: $CONFIG_FILE"
    ./build/surface_resampler "$CONFIG_FILE"
    
    # 2. Extract output file path from JSON to run visualization
    # Using python to parse JSON correctly is more robust than grep/sed
    RESULT_FILE=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['output_file'])")
    
    if [ -f "$RESULT_FILE" ]; then
        echo "Launching visualization: $RESULT_FILE..."
        python3 tools/scripts/visualize_dat.py "$RESULT_FILE" --config "$CONFIG_FILE"
    else
        echo "Warning: Output file $RESULT_FILE not found. Cannot visualize."
    fi
else
    echo "Error: build/surface_resampler not found. Please run ./build.sh first."
fi
