# MCP-GCP

MCP-GCP is a project that integrates with **MCP** and **Cursor**, enabling seamless execution of commands via `uv`.

## Setup Guide

### 1. Configure Environment Variables

1. Copy the example environment file and update the values:
   ```sh
   cp .env.example .env
   ```
2. Open `.env` in a text editor:
   ```sh
   nano .env
   ```
3. Update the required environment variables as per your setup.
4. Save and exit (in nano, press `CTRL + X`, then `Y`, then `Enter`).

---

### 2. Install Dependencies Using `uv`

This project uses [`uv`](https://github.com/astral-sh/uv) for dependency management. To install dependencies:

1. Install `uv` if you haven't:
   ```sh
   pip install uv
   ```
2. Install project dependencies:
   ```sh
   uv pip install -r requirements.txt
   ```

---

## Integration with MCP

To integrate this project with **MCP**, update the configuration file based on your OS.

### **Mac Configuration**
- File Location:  
  `~/Library/Application Support/Claude/claude_desktop_config.json`
- Add the following configuration:
  ```json
  {
      "mcpServers": {
          "mcp-gcp": {
              "command": "/Users/vuchumanh/.local/bin/uv",
              "args": [
                  "--directory",
                  "/Volumes/MrChu/local_project/mcp-gcp",
                  "run",
                  "main.py"
              ]
          }
      }
  }
  ```

### **Linux Configuration**
- File Location:  
  `~/.config/Claude/claude_desktop_config.json`
- Add the configuration (modify paths as needed):
  ```json
  {
      "mcpServers": {
          "mcp-gcp": {
              "command": "/home/yourusername/.local/bin/uv",
              "args": [
                  "--directory",
                  "/home/yourusername/projects/mcp-gcp",
                  "run",
                  "main.py"
              ]
          }
      }
  }
  ```

### **Windows Configuration**
- File Location:  
  `%APPDATA%\Claude\claude_desktop_config.json`
- Add the configuration (modify paths as needed):
  ```json
  {
      "mcpServers": {
          "mcp-gcp": {
              "command": "C:\\Users\\YourUsername\\.local\\bin\\uv.exe",
              "args": [
                  "--directory",
                  "C:\\Users\\YourUsername\\Projects\\mcp-gcp",
                  "run",
                  "main.py"
              ]
          }
      }
  }
  ```

---

## Integration with Cursor

To integrate **Cursor**, update the following configuration file.

### **Mac Configuration**
- File Location:  
  `/Users/vuchumanh/.cursor/mcp.json`
- Add the following configuration:
  ```json
  {
      "mcpServers": {
          "mcp-gcp-server": {
              "command": "/Users/vuchumanh/.local/bin/uv",
              "args": [
                  "--directory",
                  "/Volumes/MrChu/local_project/mcp-gcp",
                  "run",
                  "main.py",
                  "--transport",
                  "stdio"
              ]
          }
      }
  }
  ```

### **Linux Configuration**
- File Location:  
  `~/.cursor/mcp.json`
- Add the configuration:
  ```json
  {
      "mcpServers": {
          "mcp-gcp-server": {
              "command": "/home/yourusername/.local/bin/uv",
              "args": [
                  "--directory",
                  "/home/yourusername/projects/mcp-gcp",
                  "run",
                  "main.py",
                  "--transport",
                  "stdio"
              ]
          }
      }
  }
  ```

### **Windows Configuration**
- File Location:  
  `%APPDATA%\.cursor\mcp.json`
- Add the configuration:
  ```json
  {
      "mcpServers": {
          "mcp-gcp-server": {
              "command": "C:\\Users\\YourUsername\\.local\\bin\\uv.exe",
              "args": [
                  "--directory",
                  "C:\\Users\\YourUsername\\Projects\\mcp-gcp",
                  "run",
                  "main.py",
                  "--transport",
                  "stdio"
              ]
          }
      }
  }
  ```

---

## Running the Project

To start the MCP-GCP server, run:

```sh
uv run main.py
```

Ensure the `.env` file is correctly configured before running.

---

### **Troubleshooting**

- **Permission Issues:**  
  If you encounter permission issues with `uv`, try running:
  ```sh
  chmod +x /Users/vuchumanh/.local/bin/uv
  ```
- **Config Not Working in MCP or Cursor:**  
  - Double-check the file path.
  - Ensure JSON formatting is correct.
  - Restart MCP or Cursor after changes.

---

## License

This project is licensed under the MIT License.

