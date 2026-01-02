#!/usr/bin/env python3
"""Playwright MCP wrapper for Progressive Disclosure.

This wrapper provides browser automation capabilities via the Playwright MCP server,
spawned on-demand with connection pooling. No MCP tools are loaded into context
until explicitly needed.

Usage (CLI):
    # Navigate to a URL
    python3 playwright_wrapper.py navigate "https://example.com"

    # Take a snapshot (accessibility tree)
    python3 playwright_wrapper.py snapshot

    # Click an element
    python3 playwright_wrapper.py click --ref "button[0]" --element "Submit button"

    # Evaluate JavaScript
    python3 playwright_wrapper.py evaluate "document.title"

    # List available tools
    python3 playwright_wrapper.py --list-tools

Usage (Python):
    from playwright_wrapper import PlaywrightWrapper

    pw = PlaywrightWrapper()
    pw.navigate("https://example.com")
    snapshot = pw.snapshot()
    pw.click(ref="button[0]", element="Submit button")
    title = pw.evaluate("document.title")
    pw.close()

Prerequisites:
    - Chrome must be running with debugging enabled on port 9222
    - Launch with: google-chrome --remote-debugging-port=9222
    - Or use: dev-tools/scripts/launch-chrome-debug.sh
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path for mcp_client import
sys.path.insert(0, str(Path(__file__).parent))
from mcp_client import MCPClient


class PlaywrightWrapper:
    """Wrapper for Playwright MCP server with connection pooling."""

    DEFAULT_CDP_ENDPOINT = "http://localhost:9222"

    def __init__(
        self,
        cdp_endpoint: Optional[str] = None,
        idle_timeout: float = 60.0,
        auto_check_chrome: bool = True,
    ):
        """Initialize Playwright wrapper.

        Args:
            cdp_endpoint: Chrome DevTools Protocol endpoint (default: localhost:9222)
            idle_timeout: Seconds of inactivity before auto-terminating server
            auto_check_chrome: Check if Chrome debugging is accessible before starting
        """
        self.cdp_endpoint = cdp_endpoint or self.DEFAULT_CDP_ENDPOINT

        if auto_check_chrome and not self._check_chrome_accessible():
            raise RuntimeError(
                f"Chrome debugging endpoint not accessible at {self.cdp_endpoint}. "
                "Launch Chrome with: google-chrome --remote-debugging-port=9222 "
                "or use: ./dev-tools/scripts/launch-chrome-debug.sh"
            )

        command = [
            "npx", "-y", "@playwright/mcp@latest",
            "--cdp-endpoint", self.cdp_endpoint,
        ]

        self._client = MCPClient(
            name="playwright",
            command=command,
            idle_timeout=idle_timeout,
        )

    def _check_chrome_accessible(self) -> bool:
        """Check if Chrome debugging endpoint is accessible."""
        try:
            result = subprocess.run(
                ["curl", "-s", f"{self.cdp_endpoint}/json/version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _call(self, tool: str, **kwargs: Any) -> Any:
        """Call a Playwright MCP tool."""
        # Filter out None values
        args = {k: v for k, v in kwargs.items() if v is not None}
        return self._client.call(tool, args)

    # Navigation

    def navigate(self, url: str) -> str:
        """Navigate to a URL.

        Args:
            url: URL to navigate to

        Returns:
            Navigation result message
        """
        return self._call("browser_navigate", url=url)

    def navigate_back(self) -> str:
        """Go back to the previous page."""
        return self._call("browser_navigate_back")

    # Content Extraction

    def snapshot(self, filename: Optional[str] = None) -> str:
        """Capture accessibility snapshot of the current page.

        This is the preferred method for understanding page content
        and finding element references for interaction.

        Args:
            filename: Optional file to save snapshot to

        Returns:
            Accessibility tree as text
        """
        return self._call("browser_snapshot", filename=filename)

    def screenshot(
        self,
        filename: Optional[str] = None,
        full_page: bool = False,
        ref: Optional[str] = None,
        element: Optional[str] = None,
    ) -> str:
        """Take a screenshot of the current page.

        Args:
            filename: File name to save screenshot to
            full_page: Whether to capture full scrollable page
            ref: Element reference to screenshot (from snapshot)
            element: Human-readable element description

        Returns:
            Screenshot result message
        """
        return self._call(
            "browser_take_screenshot",
            filename=filename,
            fullPage=full_page,
            ref=ref,
            element=element,
        )

    # Interaction

    def click(
        self,
        ref: str,
        element: str,
        button: str = "left",
        double_click: bool = False,
    ) -> str:
        """Click an element.

        Args:
            ref: Element reference from snapshot (e.g., "button[0]")
            element: Human-readable element description
            button: Mouse button ("left", "right", "middle")
            double_click: Whether to double-click

        Returns:
            Click result message
        """
        return self._call(
            "browser_click",
            ref=ref,
            element=element,
            button=button,
            doubleClick=double_click if double_click else None,
        )

    def type(
        self,
        ref: str,
        element: str,
        text: str,
        submit: bool = False,
        slowly: bool = False,
    ) -> str:
        """Type text into an element.

        Args:
            ref: Element reference from snapshot
            element: Human-readable element description
            text: Text to type
            submit: Whether to press Enter after typing
            slowly: Whether to type one character at a time

        Returns:
            Type result message
        """
        return self._call(
            "browser_type",
            ref=ref,
            element=element,
            text=text,
            submit=submit if submit else None,
            slowly=slowly if slowly else None,
        )

    def hover(self, ref: str, element: str) -> str:
        """Hover over an element.

        Args:
            ref: Element reference from snapshot
            element: Human-readable element description

        Returns:
            Hover result message
        """
        return self._call("browser_hover", ref=ref, element=element)

    def select_option(self, ref: str, element: str, values: List[str]) -> str:
        """Select option(s) in a dropdown.

        Args:
            ref: Element reference from snapshot
            element: Human-readable element description
            values: Value(s) to select

        Returns:
            Select result message
        """
        return self._call("browser_select_option", ref=ref, element=element, values=values)

    def press_key(self, key: str) -> str:
        """Press a keyboard key.

        Args:
            key: Key name (e.g., "Enter", "ArrowDown", "a")

        Returns:
            Key press result message
        """
        return self._call("browser_press_key", key=key)

    # JavaScript Execution

    def evaluate(
        self,
        function: str,
        ref: Optional[str] = None,
        element: Optional[str] = None,
    ) -> Any:
        """Evaluate JavaScript expression on page or element.

        Args:
            function: JavaScript function to execute (e.g., "document.title" or "() => window.location.href")
            ref: Optional element reference to execute on
            element: Human-readable element description (required if ref is provided)

        Returns:
            JavaScript execution result
        """
        return self._call(
            "browser_evaluate",
            function=function,
            ref=ref,
            element=element,
        )

    # Waiting

    def wait_for(
        self,
        text: Optional[str] = None,
        text_gone: Optional[str] = None,
        time_seconds: Optional[float] = None,
    ) -> str:
        """Wait for a condition.

        Args:
            text: Wait for this text to appear
            text_gone: Wait for this text to disappear
            time_seconds: Wait for this many seconds

        Returns:
            Wait result message
        """
        return self._call(
            "browser_wait_for",
            text=text,
            textGone=text_gone,
            time=time_seconds,
        )

    # Tabs

    def tabs(self, action: str = "list", index: Optional[int] = None) -> str:
        """Manage browser tabs.

        Args:
            action: "list", "new", "close", or "select"
            index: Tab index for close/select actions

        Returns:
            Tab operation result
        """
        return self._call("browser_tabs", action=action, index=index)

    # Page State

    def console_messages(self, level: str = "info") -> str:
        """Get console messages.

        Args:
            level: Minimum level ("error", "warning", "info", "debug")

        Returns:
            Console messages
        """
        return self._call("browser_console_messages", level=level)

    def network_requests(self, include_static: bool = False) -> str:
        """Get network requests since page load.

        Args:
            include_static: Whether to include static resources

        Returns:
            Network request log
        """
        return self._call("browser_network_requests", includeStatic=include_static)

    # Forms

    def fill_form(self, fields: List[Dict[str, str]]) -> str:
        """Fill multiple form fields at once.

        Args:
            fields: List of field dicts with keys: name, type, ref, value
                   type can be: textbox, checkbox, radio, combobox, slider

        Returns:
            Form fill result
        """
        return self._call("browser_fill_form", fields=fields)

    def file_upload(self, paths: Optional[List[str]] = None) -> str:
        """Upload file(s) or cancel file chooser.

        Args:
            paths: Absolute paths to files. If omitted, cancels chooser.

        Returns:
            Upload result message
        """
        return self._call("browser_file_upload", paths=paths)

    # Dialog Handling

    def handle_dialog(self, accept: bool, prompt_text: Optional[str] = None) -> str:
        """Handle a browser dialog (alert, confirm, prompt).

        Args:
            accept: Whether to accept the dialog
            prompt_text: Text to enter for prompt dialogs

        Returns:
            Dialog handling result
        """
        return self._call(
            "browser_handle_dialog",
            accept=accept,
            promptText=prompt_text,
        )

    # Lifecycle

    def resize(self, width: int, height: int) -> str:
        """Resize the browser window.

        Args:
            width: Window width in pixels
            height: Window height in pixels

        Returns:
            Resize result message
        """
        return self._call("browser_resize", width=width, height=height)

    def close(self) -> str:
        """Close the current browser page."""
        result = self._call("browser_close")
        return result

    def shutdown(self) -> None:
        """Shutdown the MCP client (terminates server after idle timeout)."""
        self._client.close()

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from this server."""
        return self._client.get_tools()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Playwright MCP wrapper for browser automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s navigate "https://example.com"
  %(prog)s snapshot
  %(prog)s click --ref "button[0]" --element "Submit button"
  %(prog)s type --ref "input[0]" --element "Search box" --text "hello"
  %(prog)s evaluate "document.title"
  %(prog)s wait --time 2
  %(prog)s --list-tools
        """,
    )

    parser.add_argument(
        "--cdp-endpoint",
        default=PlaywrightWrapper.DEFAULT_CDP_ENDPOINT,
        help="Chrome DevTools Protocol endpoint",
    )
    parser.add_argument(
        "--no-check-chrome",
        action="store_true",
        help="Skip Chrome accessibility check",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    subparsers = parser.add_subparsers(dest="command")

    # navigate
    p_nav = subparsers.add_parser("navigate", help="Navigate to a URL")
    p_nav.add_argument("url", help="URL to navigate to")

    # snapshot
    p_snap = subparsers.add_parser("snapshot", help="Capture accessibility snapshot")
    p_snap.add_argument("--filename", help="Save snapshot to file")

    # screenshot
    p_shot = subparsers.add_parser("screenshot", help="Take a screenshot")
    p_shot.add_argument("--filename", help="Save screenshot to file")
    p_shot.add_argument("--full-page", action="store_true", help="Capture full page")
    p_shot.add_argument("--ref", help="Element reference")
    p_shot.add_argument("--element", help="Element description")

    # click
    p_click = subparsers.add_parser("click", help="Click an element")
    p_click.add_argument("--ref", required=True, help="Element reference from snapshot")
    p_click.add_argument("--element", required=True, help="Element description")
    p_click.add_argument("--button", default="left", choices=["left", "right", "middle"])
    p_click.add_argument("--double", action="store_true", help="Double-click")

    # type
    p_type = subparsers.add_parser("type", help="Type text into an element")
    p_type.add_argument("--ref", required=True, help="Element reference")
    p_type.add_argument("--element", required=True, help="Element description")
    p_type.add_argument("--text", required=True, help="Text to type")
    p_type.add_argument("--submit", action="store_true", help="Press Enter after")
    p_type.add_argument("--slowly", action="store_true", help="Type one char at a time")

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Evaluate JavaScript")
    p_eval.add_argument("function", help="JavaScript to execute")
    p_eval.add_argument("--ref", help="Element reference")
    p_eval.add_argument("--element", help="Element description")

    # wait
    p_wait = subparsers.add_parser("wait", help="Wait for a condition")
    p_wait.add_argument("--text", help="Wait for text to appear")
    p_wait.add_argument("--text-gone", help="Wait for text to disappear")
    p_wait.add_argument("--time", type=float, help="Wait for seconds")

    # close
    subparsers.add_parser("close", help="Close the browser page")

    # back
    subparsers.add_parser("back", help="Go back to previous page")

    # tabs
    p_tabs = subparsers.add_parser("tabs", help="Manage browser tabs")
    p_tabs.add_argument("action", choices=["list", "new", "close", "select"])
    p_tabs.add_argument("--index", type=int, help="Tab index for close/select")

    args = parser.parse_args()

    def output(result: Any) -> None:
        if args.json:
            print(json.dumps(result, indent=2) if isinstance(result, (dict, list)) else json.dumps(result))
        else:
            print(result)

    try:
        pw = PlaywrightWrapper(
            cdp_endpoint=args.cdp_endpoint,
            auto_check_chrome=not args.no_check_chrome,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        if args.list_tools:
            tools = pw.get_tools()
            for tool in tools:
                name = tool.get("name", "unknown")
                desc = tool.get("description", "No description")
                print(f"- {name}: {desc}")
            return 0

        if args.command == "navigate":
            output(pw.navigate(args.url))
        elif args.command == "snapshot":
            output(pw.snapshot(filename=args.filename))
        elif args.command == "screenshot":
            output(pw.screenshot(
                filename=args.filename,
                full_page=args.full_page,
                ref=args.ref,
                element=args.element,
            ))
        elif args.command == "click":
            output(pw.click(
                ref=args.ref,
                element=args.element,
                button=args.button,
                double_click=args.double,
            ))
        elif args.command == "type":
            output(pw.type(
                ref=args.ref,
                element=args.element,
                text=args.text,
                submit=args.submit,
                slowly=args.slowly,
            ))
        elif args.command == "evaluate":
            output(pw.evaluate(
                function=args.function,
                ref=args.ref,
                element=args.element,
            ))
        elif args.command == "wait":
            output(pw.wait_for(
                text=args.text,
                text_gone=args.text_gone,
                time_seconds=args.time,
            ))
        elif args.command == "close":
            output(pw.close())
        elif args.command == "back":
            output(pw.navigate_back())
        elif args.command == "tabs":
            output(pw.tabs(action=args.action, index=args.index))
        else:
            parser.print_help()
            return 1

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    finally:
        # Don't explicitly shutdown - let idle timeout handle it
        # This allows multiple CLI calls to reuse the connection
        pass


if __name__ == "__main__":
    sys.exit(main())
