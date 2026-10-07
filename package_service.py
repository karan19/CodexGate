"""Bundled service entry point; runtime state stays outside the signed bundle."""
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('broker', 'launch'):
        raise SystemExit('Expected broker or launch')
    mode = sys.argv.pop(1)
    if mode == 'broker':
        import file_broker
        file_broker.main()
    else:
        import launch_desktop
        # sandbox_launcher.PROJECT is a source path in development; a frozen
        # distribution writes policies/runtime only to user application data.
        launch_desktop.PROJECT = Path.home() / 'Library/Application Support/CodexGate/menu-bar'
        import managed_launch
        managed_launch.main()

if __name__ == '__main__':
    main()
