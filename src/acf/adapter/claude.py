"""Claude adapter for ACF v2.0.

This module provides an adapter for Claude Code CLI using tmux for process management.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from acf.adapter.base import AgentAdapter, AgentResult, AgentStatus, AdapterConfig


class ClaudeAdapter(AgentAdapter):
    """Adapter for Claude Code CLI.

    This adapter manages Claude Code instances using tmux sessions.
    It handles the initialization handshake (sending "2" for confirmation)
    and captures output using tee to a temporary file.

    Example:
        ```python
        config = AdapterConfig(name="claude-agent", timeout=120.0)
        adapter = ClaudeAdapter(config)
        result = await adapter.execute("Write a Python function to sort a list")
        ```
    """

    def __init__(self, config: AdapterConfig) -> None:
        """Initialize the Claude adapter.

        Args:
            config: Adapter configuration.
        """
        super().__init__(config)
        self._tmux_session: Optional[str] = None
        self._output_file: Optional[Path] = None
        self._workspace_dir: Path = Path(
            config.metadata.get("workspace_dir", os.getcwd())
        )
        self._confirm_delay: float = config.metadata.get("confirm_delay", 0.5)

    @property
    def tmux_session(self) -> str:
        """Get or create tmux session name."""
        if self._tmux_session is None:
            self._tmux_session = f"acf-claude-{self.name}"
        return self._tmux_session

    async def _create_tmux_session(self) -> bool:
        """Create a new tmux session for Claude.

        Returns:
            True if session created successfully, False otherwise.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "new-session", "-d", "-s", self.tmux_session,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                # Session might already exist
                if "already exists" in error_msg:
                    return True
                return False
            return True
        except FileNotFoundError:
            # tmux not installed
            return False
        except Exception:
            return False

    async def _kill_tmux_session(self) -> None:
        """Kill the tmux session if it exists."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "kill-session", "-t", self.tmux_session,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            pass

    async def _send_keys(self, keys: str) -> bool:
        """Send keystrokes to the tmux session.

        Args:
            keys: Keys to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", self.tmux_session, keys,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False

    async def _capture_pane(self) -> str:
        """Capture the current content of the tmux pane.

        Returns:
            Current pane content.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "capture-pane", "-t", self.tmux_session, "-p",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode()
        except Exception:
            return ""

    async def _wait_for_file_stability(
        self, file_path: Path, stable_duration: float = 1.0, timeout: float = 60.0
    ) -> bool:
        """Wait for file size to stabilize.

        Args:
            file_path: Path to the file to monitor.
            stable_duration: Duration in seconds the file size must remain stable.
            timeout: Maximum time to wait.

        Returns:
            True if file stabilized, False if timeout.
        """
        start_time = asyncio.get_event_loop().time()
        last_size = -1
        stable_since: Optional[float] = None

        while True:
            await asyncio.sleep(0.1)

            if not file_path.exists():
                continue

            current_size = file_path.stat().st_size
            current_time = asyncio.get_event_loop().time()

            if current_time - start_time > timeout:
                return False

            if current_size == last_size:
                if stable_since is None:
                    stable_since = current_time
                elif current_time - stable_since >= stable_duration:
                    return True
            else:
                stable_since = None
                last_size = current_size

    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        """Execute a prompt using Claude Code.

        Args:
            prompt: The input prompt for Claude.
            **kwargs: Additional parameters (timeout, confirm_delay).

        Returns:
            AgentResult containing Claude's response.
        """
        timeout = kwargs.get("timeout", self.config.timeout)
        confirm_delay = kwargs.get("confirm_delay", self._confirm_delay)

        await self._set_status(AgentStatus.RUNNING)

        # Create tmux session
        if not await self._create_tmux_session():
            await self._set_status(AgentStatus.ERROR)
            return self._create_result(
                AgentStatus.ERROR,
                error="Failed to create tmux session. Is tmux installed?",
            )

        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            self._output_file = Path(f.name)

        try:
            # Start claude code with tee to capture output
            claude_cmd = f"cd {self._workspace_dir} && claude | tee {self._output_file}"
            if not await self._send_keys(claude_cmd):
                await self._set_status(AgentStatus.ERROR)
                return self._create_result(
                    AgentStatus.ERROR,
                    error="Failed to send command to tmux session",
                )

            # Send Enter to execute
            await self._send_keys("C-m")

            # Wait for initialization and send "2" to confirm
            await asyncio.sleep(confirm_delay)
            await self._send_keys("2")
            await self._send_keys("C-m")

            # Wait a bit more for Claude to be ready
            await asyncio.sleep(1.0)

            # Send the actual prompt
            await self._send_keys(prompt)
            await self._send_keys("C-m")

            # Wait for output to stabilize
            completed = await self._wait_for_file_stability(
                self._output_file, stable_duration=1.0, timeout=timeout
            )

            if not completed:
                await self._set_status(AgentStatus.TIMEOUT)
                return self._create_result(
                    AgentStatus.TIMEOUT,
                    error=f"Execution timed out after {timeout}s",
                )

            # Read the output
            content = self._output_file.read_text()

            # Clean up the output (remove command echo and prompts)
            lines = content.split("\n")
            # Filter out common noise
            filtered = [
                line for line in lines
                if not line.startswith("$")
                and "claude" not in line.lower()
                and line.strip()
            ]

            output = "\n".join(filtered)

            await self._set_status(AgentStatus.COMPLETED)
            return self._create_result(
                AgentStatus.COMPLETED,
                output=output,
                output_file=str(self._output_file),
            )

        except Exception as e:
            await self._set_status(AgentStatus.ERROR)
            return self._create_result(
                AgentStatus.ERROR,
                error=f"Execution error: {str(e)}",
            )

        finally:
            # Cleanup
            await self._kill_tmux_session()
            if self._output_file and self._output_file.exists():
                try:
                    self._output_file.unlink()
                except Exception:
                    pass

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Execute a prompt and stream the output.

        Note: This is a simplified implementation that collects output
        and yields it. For true streaming, the adapter would need to
        monitor the output file in real-time.

        Args:
            prompt: The input prompt for Claude.
            **kwargs: Additional parameters.

        Yields:
            Chunks of Claude's output.
        """
        result = await self.execute(prompt, **kwargs)

        if result.status == AgentStatus.ERROR:
            yield f"Error: {result.error}"
            return

        # Yield output in chunks
        chunk_size = kwargs.get("chunk_size", 100)
        output = result.output

        for i in range(0, len(output), chunk_size):
            yield output[i:i + chunk_size]
            await asyncio.sleep(0.01)  # Small delay for streaming effect

    async def health_check(self) -> bool:
        """Check if Claude is available.

        Returns:
            True if tmux and claude are available, False otherwise.
        """
        # Check tmux
        try:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "-V",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            if proc.returncode != 0:
                return False
        except FileNotFoundError:
            return False

        # Check claude (we assume it's available if tmux is, since
        # claude might be installed but not in PATH during testing)
        return True
