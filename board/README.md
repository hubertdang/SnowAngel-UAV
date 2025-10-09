# Project Setup

## Prerequisites

This project requires the following tools to be installed on your system:

- **GCC** – C compiler  
- **G++** – C++ compiler  
- **clang-format** – Code formatter  
- **clangd** – Language server for C/C++ (used by IDEs like VS Code)

## Installation

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install build-essential clang-format clangd -y
```

### macOS (with Homebrew)
```bash
brew install gcc clang-format clangd
```

### Verify Installation
```bash
gcc --version
g++ --version
clang-format --version
clangd --version
```

### Note
On VS Code, make you see clangd at the bottom left of your screen on your status bar. If you don't, reload your editor.
