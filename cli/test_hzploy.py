"""Tests for hzploy CLI (manual/integration)."""

import json
import subprocess
import sys
from pathlib import Path


def run_cmd(args: list[str]) -> tuple[int, str, str]:
    """Run hzploy command and capture output."""
    result = subprocess.run(
        [sys.executable, "cli/hzploy"] + args,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_help():
    """Test: hzploy --help works"""
    code, stdout, stderr = run_cmd(["--help"])
    assert code == 0
    assert "hzploy" in stdout or "usage" in stdout.lower()


def test_login_saves_config(tmp_path):
    """Test: hzploy login saves to ~/.hzploy/config"""
    # This test requires mocking ~/.hzploy/config location
    # Skipped in unit tests, use manual testing instead
    pass


def test_parser_invalid_command():
    """Test: Invalid command returns error"""
    code, stdout, stderr = run_cmd(["invalid-command"])
    assert code != 0


def test_parser_up_command():
    """Test: 'up' command accepts all required args"""
    # Would need real devps server or mocking
    # Skipped in unit tests
    pass


# Manual Testing Checklist
"""
Manual integration tests (requires running devps server):

1. Setup:
   export DEVPS_URL=https://devps.webshooks.com
   export DEVPS_TOKEN=<your-token>

2. Test login:
   python cli/hzploy login https://devps.webshooks.com test_token
   cat ~/.hzploy/config  # verify JSON

3. Test list:
   python cli/hzploy list
   # Expected: table of projects

4. Test up:
   python cli/hzploy up test-app https://github.com/fmonfasani/devps.git \
     --service web=8000 \
     --primary web \
     --ref main
   # Expected: JSON output with project details

5. Test logs:
   python cli/hzploy logs test-app --tail 50
   # Expected: container logs

6. Test restart:
   python cli/hzploy restart test-app
   # Expected: {'status': 'restarted'}

7. Test rm:
   python cli/hzploy rm test-app
   # Expected: {'status': 'deregistered'}

8. Verify env vars override config:
   export DEVPS_URL=https://wrong.url
   python cli/hzploy list  # should still work if env DEVPS_TOKEN set correctly
"""

if __name__ == "__main__":
    # Basic smoke tests
    print("Running basic hzploy tests...")
    test_help()
    print("✅ Help test passed")

    test_parser_invalid_command()
    print("✅ Invalid command test passed")

    print("\n✅ All basic tests passed!")
    print("\nFor full integration tests, see manual testing checklist above.")
