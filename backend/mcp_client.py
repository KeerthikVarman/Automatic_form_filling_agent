import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from typing import Dict, Any, Optional, List

logger = logging.getLogger("mcp_client")
logger.setLevel(logging.INFO)

class PlaywrightMCPClient:
    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._tools: List[Dict[str, Any]] = []
        self.is_connected = False
        self.current_url = ""
        self.last_snapshot_text = ""

    def _get_next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def start(self) -> bool:
        """Launch Playwright MCP server process and initialize MCP protocol."""
        if self.is_connected and self.proc and self.proc.poll() is None:
            logger.info("Playwright MCP server is already running.")
            return True

        # Locate Playwright MCP binary or script
        node_bin = shutil.which("node") or "node"
        npm_global_cli = os.path.expandvars(r"%APPDATA%\npm\node_modules\@playwright\mcp\cli.js")
        
        cmd = []
        if os.path.exists(npm_global_cli):
            # Direct node invocation
            # Headed browser by default (visible) with isolated context
            cmd = [node_bin, npm_global_cli, "--isolated"]
        else:
            npx_bin = shutil.which("npx") or "npx"
            cmd = [npx_bin, "@playwright/mcp@latest", "--isolated"]

        logger.info(f"Starting Playwright MCP with command: {' '.join(cmd)}")

        try:
            # Using subprocess.Popen with thread-based async I/O
            # Completely immune to Windows asyncio SelectorEventLoop NotImplementedError
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self._reader_task = asyncio.create_task(self._read_stdout())
            self.is_connected = True

            # 1. Initialize MCP
            init_response = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "udyam-ai-assistant",
                        "version": "1.0.0"
                    }
                },
                timeout=20.0
            )
            logger.info(f"MCP Initialized: {init_response.get('result', {}).get('serverInfo')}")

            # 2. Send initialized notification
            await self._send_notification("notifications/initialized", {})

            # 3. List available tools
            tools_resp = await self._send_request("tools/list", {}, timeout=15.0)
            self._tools = tools_resp.get("result", {}).get("tools", [])
            tool_names = [t.get("name") for t in self._tools]
            logger.info(f"Discovered {len(self._tools)} Playwright MCP tools: {', '.join(tool_names)}")

            return True

        except Exception as e:
            logger.error(f"Failed to start Playwright MCP client: {e}", exc_info=True)
            await self.stop()
            return False

    async def _read_stdout(self):
        """Continuously read lines from the MCP server stdout in a thread."""
        while self.proc and self.proc.poll() is None:
            try:
                line = await asyncio.to_thread(self.proc.stdout.readline)
                if not line:
                    break
                raw = line.decode("utf-8").strip()
                if not raw:
                    continue

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # Handle response to request
                req_id = data.get("id")
                if req_id is not None and req_id in self._pending_requests:
                    future = self._pending_requests.pop(req_id)
                    if not future.done():
                        future.set_result(data)
                elif "method" in data:
                    # Server notification
                    logger.debug(f"MCP Notification: {data.get('method')}")
            except Exception as e:
                logger.error(f"Error reading from MCP stdout: {e}")
                break

    async def _send_request(self, method: str, params: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """Send a JSON-RPC request and await response."""
        if not self.proc or self.proc.poll() is not None:
            raise RuntimeError("MCP process is not running")

        req_id = self._get_next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_requests[req_id] = future

        msg = (json.dumps(payload) + "\n").encode("utf-8")
        def _write():
            self.proc.stdin.write(msg)
            self.proc.stdin.flush()

        await asyncio.to_thread(_write)

        try:
            resp = await asyncio.wait_for(future, timeout=timeout)
            if "error" in resp:
                raise RuntimeError(f"MCP RPC Error: {resp['error']}")
            return resp
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise TimeoutError(f"Request {method} (id={req_id}) timed out after {timeout}s")

    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """Send a JSON-RPC notification (no response expected)."""
        if not self.proc or self.proc.poll() is not None:
            return
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        msg = (json.dumps(payload) + "\n").encode("utf-8")
        def _write():
            self.proc.stdin.write(msg)
            self.proc.stdin.flush()

        await asyncio.to_thread(_write)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 45.0) -> Dict[str, Any]:
        """Invoke a Playwright MCP tool."""
        res = await self._send_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments
            },
            timeout=timeout
        )
        return res.get("result", {})

    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL using browser_navigate."""
        logger.info(f"Navigating to URL: {url}")
        res = await self.call_tool("browser_navigate", {"url": url}, timeout=60.0)
        self.current_url = url
        return res

    async def snapshot(self) -> Dict[str, Any]:
        """Capture the accessibility snapshot of the current page."""
        res = await self.call_tool("browser_snapshot", {}, timeout=20.0)
        content_items = res.get("content", [])
        snapshot_text = ""
        for item in content_items:
            if item.get("type") == "text":
                snapshot_text += item.get("text", "")

        self.last_snapshot_text = snapshot_text
        # Parse Page URL if present in snapshot text
        for line in snapshot_text.splitlines():
            if line.startswith("- Page URL:"):
                self.current_url = line.replace("- Page URL:", "").strip()
                break

        return {
            "url": self.current_url,
            "snapshot_text": snapshot_text,
            "raw": res
        }

    async def fill_form(self, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fill form fields via browser_fill_form."""
        formatted_fields = []
        for f in fields:
            formatted_fields.append({
                "target": f.get("target") or f.get("ref", ""),
                "name": f.get("name", "field"),
                "type": f.get("type", "textbox"),
                "value": str(f.get("value", ""))
            })
        return await self.call_tool("browser_fill_form", {"fields": formatted_fields}, timeout=20.0)

    async def type_element(self, element_ref: str, text: str) -> Dict[str, Any]:
        """Type text into element using browser_type with target property."""
        return await self.call_tool("browser_type", {"target": element_ref, "text": text}, timeout=15.0)

    async def click_element(self, element_ref: str) -> Dict[str, Any]:
        """Click element using browser_click with target property."""
        return await self.call_tool("browser_click", {"target": element_ref}, timeout=15.0)

    async def evaluate_script(self, expression: str) -> Dict[str, Any]:
        """Evaluate JS expression in page."""
        return await self.call_tool("browser_evaluate", {"expression": expression}, timeout=15.0)

    async def stop(self):
        """Shut down the Playwright MCP server."""
        self.is_connected = False
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
        if self.proc:
            try:
                self.proc.terminate()
                await asyncio.to_thread(self.proc.wait, 3.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        logger.info("Playwright MCP stopped.")
