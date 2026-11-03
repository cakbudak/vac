"""Write this process id to a file, then exec the real server command in place.

The MCP SDK's stdio client does not expose the child's pid; exec-ing keeps the
pid identical, so the harness can watch /proc/<pid> for child processes and
sockets while a tool call is in flight.
"""
import os
import sys

pidfile, cmd = sys.argv[1], sys.argv[2:]
with open(pidfile, "w") as f:
    f.write(str(os.getpid()))
os.execvp(cmd[0], cmd)
