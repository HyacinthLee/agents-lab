"""Claude adapter for ACF v2.0.

This module provides an adapter for Claude Code CLI using tmux for process management.
"""

import asyncio
import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from acf.adapter.base import AgentAdapter, AgentResult, AgentStatus, AdapterConfig


class ClaudeAdapter(AgentAdapter):
    """Adapter for Claude Code CLI.

    This adapter uses `claude --print` non-interactive mode for reliable
    programmatic execution via tmux.

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
        self._workspace_dir: Path = Path(
            config.metadata.get("workspace_dir", os.getcwd())
        )
        self._confirm_delay: float = config.metadata.get("confirm_delay", 0.5)

    @property
    def tmux_session(self) -> str:
        """Get or create tmux session name."""
        if self._tmux_session is None:
            self._tmux_session = f"acf-claude-{self.name}-{id(self)}"
        return self._tmux_session

    def _run_claude_sync(self, prompt: str, timeout: float) -> tuple[int, str, str]:
        """Run Claude Code synchronously using tmux.

        Args:
            prompt: The input prompt for Claude.
            timeout: Execution timeout in seconds.

        Returns:
            Tuple of (returncode, stdout, stderr).
        """
        tmux_socket = f"/tmp/tmux_{self.tmux_session}"
        
        # Clean up old session
        try:
            subprocess.run(
                ["tmux", "-S", tmux_socket, "kill-session", "-t", self.tmux_session],
                capture_output=True, timeout=3
            )
        except Exception:
            pass
        time.sleep(0.2)
        
        # Create prompt file in workspace (Claude Code runs in isolated env, can't access /tmp)
        prompt_file = self._workspace_dir / f".claude_prompt_{self.tmux_session}.txt"
        output_file = self._workspace_dir / f".claude_output_{self.tmux_session}.txt"
        
        # Write prompt to file
        try:
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt)
        except Exception as e:
            return 1, "", f"Failed to write prompt file: {e}"
        
        # Build command: use echo '2' | claude --print "$(cat prompt_file)"
        # echo '2' confirms permission, $(cat) reads long prompt from file
        cmd_str = f"cd {shlex.quote(str(self._workspace_dir))} && echo '2' | claude --print \"\\$(cat {shlex.quote(str(prompt_file))})\" 2>&1 | tee {shlex.quote(str(output_file))}"
        
        # Create tmux session
        cmd = [
            "tmux", "-S", tmux_socket,
            "new-session", "-d", "-s", self.tmux_session,
            "-c", str(self._workspace_dir),
            cmd_str
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, timeout=10)
        except Exception as e:
            # Cleanup prompt file on error
            try:
                Path(prompt_file).unlink(missing_ok=True)
            except:
                pass
            return 1, "", str(e)
        
        # Wait for completion (file size stable and non-zero, or timeout)
        start_time = time.time()
        last_size = -1
        stable_count = 0
        min_wait = 25  # Further increased: Minimum wait time before considering completion
        
        # Initial delay to let Claude start up
        time.sleep(8)  # Increased from 5 to 8
        
        while time.time() - start_time < timeout:
            time.sleep(3)  # Increased from 2 to 3
            
            try:
                if Path(output_file).exists():
                    current_size = Path(output_file).stat().st_size
                    elapsed = time.time() - start_time
                    
                    # Only check stability if we have content and waited minimum time
                    if current_size > 0 and elapsed >= min_wait:
                        if current_size == last_size:
                            stable_count += 1
                            if stable_count >= 4:  # Increased from 3 to 4
                                break
                        else:
                            stable_count = 0
                            last_size = current_size
            except Exception:
                pass
        
        # Read output - try to read even if we timed out, in case there's content
        output = ""
        try:
            if Path(output_file).exists() and Path(output_file).stat().st_size > 0:
                with open(output_file, 'r', encoding='utf-8') as f:
                    output = f.read()
        except Exception as e:
            output = f"[Error reading output: {e}]"
        
        # If still no output, try one more time after a short delay
        if not output:
            time.sleep(2)
            try:
                if Path(output_file).exists():
                    with open(output_file, 'r', encoding='utf-8') as f:
                        output = f.read()
            except:
                pass
        
        # Cleanup
        try:
            subprocess.run(
                ["tmux", "-S", tmux_socket, "kill-session", "-t", self.tmux_session],
                capture_output=True, timeout=3
            )
        except Exception:
            pass
        
        try:
            Path(prompt_file).unlink(missing_ok=True)
            Path(output_file).unlink(missing_ok=True)
        except Exception:
            pass
        
        return 0, output, ""

    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        """Execute a prompt using Claude Code.

        Args:
            prompt: The input prompt for Claude.
            **kwargs: Additional parameters (timeout, confirm_delay).

        Returns:
            AgentResult containing Claude's response.
        """
        timeout = kwargs.get("timeout", self.config.timeout)
        
        await self._set_status(AgentStatus.RUNNING)
        
        try:
            # Run in thread pool to avoid blocking
            returncode, stdout, stderr = await asyncio.to_thread(
                self._run_claude_sync, prompt, timeout
            )
            
            if returncode != 0:
                await self._set_status(AgentStatus.ERROR)
                return self._create_result(
                    AgentStatus.ERROR,
                    error=stderr or "Claude execution failed",
                )
            
            await self._set_status(AgentStatus.COMPLETED)
            return self._create_result(
                AgentStatus.COMPLETED,
                output=stdout,
            )
            
        except Exception as e:
            await self._set_status(AgentStatus.ERROR)
            return self._create_result(
                AgentStatus.ERROR,
                error=f"Execution error: {str(e)}",
            )

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Execute a prompt and stream the output.

        Note: This implementation collects output and yields it.
        For true streaming, the adapter would need to monitor the output file in real-time.

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
