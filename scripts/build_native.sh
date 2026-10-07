#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p .build/native-module-cache
xcrun swiftc native/Authenticate.swift -o .build/authenticate -module-cache-path .build/native-module-cache -framework AppKit -framework LocalAuthentication
