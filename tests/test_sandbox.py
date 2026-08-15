import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import asyncio
from config import config
from core.tools import SandboxTools

async def main():
    ok, path = config.ensure_sandbox_env()
    print(f"[1] Sandbox ensure result: {ok}, Path: {path}")

    # Test running python command
    res = await SandboxTools.run_command('python -c "import sys; print(sys.executable)"')
    print("[2] run_command output:\n" + res.to_string())

    # Verify that the executable used by run_command contains 'sandbox_env'
    assert "sandbox_env" in res.output.lower(), "Executable should point to sandbox_env!"
    print("[SUCCESS] Verification passed: AI command strictly executed inside sandbox_env!")

if __name__ == "__main__":
    asyncio.run(main())

