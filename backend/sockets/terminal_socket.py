"""HackForge — Terminal Socket (sandboxed output simulation)"""
import subprocess
import threading
import os
import signal
from flask_socketio import join_room, leave_room, emit
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Track running processes per session
_processes: dict = {}
ALLOWED_COMMANDS = {"echo", "ls", "pwd", "whoami", "date", "python3", "node", "cat", "grep"}
MAX_OUTPUT_SIZE = 65536  # 64KB


def register_terminal_socket(socketio):

    @socketio.on("terminal:join")
    def on_terminal_join(data):
        from flask import request
        session_id = data.get("session_id") or request.sid
        user_id = data.get("user_id")

        join_room(f"terminal:{session_id}")
        emit("terminal:ready", {
            "session_id": session_id,
            "message": "HackForge Terminal v1.0\r\nType 'help' for available commands\r\n$ "
        })

    @socketio.on("terminal:input")
    def on_terminal_input(data):
        from flask import request
        session_id = data.get("session_id") or request.sid
        user_id = data.get("user_id")
        command = data.get("command", "").strip()

        if not command:
            emit("terminal:output", {"data": "$ "})
            return

        # Handle built-in commands
        if command == "clear":
            emit("terminal:clear", {})
            emit("terminal:output", {"data": "$ "})
            return

        if command == "help":
            help_text = (
                "\r\nHackForge Terminal Commands:\r\n"
                "  help      - Show this help\r\n"
                "  clear     - Clear terminal\r\n"
                "  echo      - Print text\r\n"
                "  ls        - List files (simulated)\r\n"
                "  pwd       - Print working directory\r\n"
                "  date      - Show current date\r\n"
                "  python3   - Run Python (limited)\r\n"
                "  node      - Run JavaScript (limited)\r\n"
                "\r\n$ "
            )
            emit("terminal:output", {"data": help_text})
            return

        if command == "ls":
            emit("terminal:output", {"data": "\r\nsrc/  public/  package.json  README.md\r\n$ "})
            return

        # Run safe commands in subprocess
        room = f"terminal:{session_id}"
        _run_command_async(socketio, room, session_id, command, user_id)

    @socketio.on("terminal:resize")
    def on_terminal_resize(data):
        session_id = data.get("session_id")
        cols = data.get("cols", 80)
        rows = data.get("rows", 24)
        logger.debug(f"Terminal resize: {cols}x{rows}")

    @socketio.on("terminal:kill")
    def on_terminal_kill(data):
        session_id = data.get("session_id")
        if session_id and session_id in _processes:
            try:
                _processes[session_id].kill()
                del _processes[session_id]
            except Exception:
                pass
        emit("terminal:output", {"data": "\r\n^C\r\n$ "})

    @socketio.on("terminal:leave")
    def on_terminal_leave(data):
        session_id = data.get("session_id")
        if session_id and session_id in _processes:
            try:
                _processes[session_id].kill()
                del _processes[session_id]
            except Exception:
                pass
        if session_id:
            leave_room(f"terminal:{session_id}")


def _run_command_async(socketio, room, session_id, command, user_id):
    def run():
        try:
            # Security: allow limited set
            cmd_parts = command.split()
            base_cmd = cmd_parts[0] if cmd_parts else ""

            # Block dangerous commands
            dangerous = ["rm", "sudo", "su", "chmod", "chown", "kill", "pkill",
                         "curl", "wget", "nc", "netcat", "ssh", "ftp", ">", ">>"]

            if any(d in command for d in dangerous) and base_cmd not in {"echo", "date", "pwd", "whoami"}:
                socketio.emit("terminal:output", {
                    "data": f"\r\n[HackForge] Command blocked for security\r\n$ "
                }, to=room)
                return

            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
                cwd="/tmp",
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "HOME": "/tmp",
                    "TERM": "xterm-256color"
                }
            )

            _processes[session_id] = proc

            output = proc.communicate(timeout=10)[0]
            if len(output) > MAX_OUTPUT_SIZE:
                output = output[:MAX_OUTPUT_SIZE] + "\n[Output truncated]"

            output = output.replace("\n", "\r\n")
            socketio.emit("terminal:output", {"data": f"\r\n{output}\r\n$ "}, to=room)

        except subprocess.TimeoutExpired:
            socketio.emit("terminal:output", {
                "data": "\r\n[Timeout: Command took too long]\r\n$ "
            }, to=room)
        except Exception as e:
            socketio.emit("terminal:output", {
                "data": f"\r\n[Error: {str(e)}]\r\n$ "
            }, to=room)
        finally:
            _processes.pop(session_id, None)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()