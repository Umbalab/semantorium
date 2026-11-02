# Semantorium for macOS

Requirements: macOS Big Sur 11.0 or newer. Intel (x86_64) and Apple Silicon (arm64) supported.

## Usage (zip, no install)
1. Download Semantorium-macOS-<arch>.zip
2. Unzip it
3. Open Semantorium.app (if Gatekeeper blocks it, right-click → Open once)

All dependencies are bundled. No system Python/packages required.

## Build from source
`ash
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller
python3 packaging/scripts/build_universal.py
`