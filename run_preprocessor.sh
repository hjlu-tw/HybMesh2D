#!/bin/bash

# Default configuration file
CONFIG_FILE=${1:-"tools/PreProcessor/config/test_curve_config.json"}

# 1. Run surface_resampler (if compiled)
if [ -f "build/surface_resampler" ]; then
    echo "Running surface_resampler with config: $CONFIG_FILE"
    ./build/surface_resampler "$CONFIG_FILE"
    
    # 2. Run visualization
    # The updated visualize_dat.py can now read 'elements' from the config
    echo "Launching multi-element visualization..."
    python3 tools/scripts/visualize_dat.py --config "$CONFIG_FILE"
else
    echo "Error: build/surface_resampler not found. Please run ./build.sh first."
fi
