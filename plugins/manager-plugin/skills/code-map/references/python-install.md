# Installing Python

Read by the code-map skill when no Python 3.8 or later is found (**Command**).

No Python → offer to install it, once, with the command for the OS. Install only after the owner
agrees in this conversation; if they decline, skip the map (the vault and the rules block don't
need it; write the block by hand).
- **Windows:** `winget install -e --id Python.Python.3.12 --scope user` (no admin rights needed).
  The current session's PATH may not see it yet. Check
  `"$LOCALAPPDATA/Programs/Python/Python312/python.exe" --version` and use that path; if it isn't
  there, say that a new session will pick Python up.
- **macOS:** `brew install python` if Homebrew exists, else the installer from python.org (the
  owner runs it).
- **Linux:** `sudo apt-get install -y python3` or the distribution's equivalent (the owner runs
  it).
