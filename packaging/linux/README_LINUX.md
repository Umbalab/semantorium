# Semantorium for Linux

## Usage (zip/tar.gz, no install)
1. Download Semantorium-Linux-<arch>.tar.gz or .zip
2. Extract it
3. Run ./Semantorium

All dependencies are bundled. No system Python/packages required.

## Build from source
`ash
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller
python3 packaging/scripts/build_universal.py
`