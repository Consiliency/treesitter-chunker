#!/usr/bin/env -S uv run --script
# /// script
# requires = { python = ">=3.8" }
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
Test script to verify multi-instance safety of the send_event hook.
"""

import json
import subprocess
import sys
import threading
from pathlib import Path


def test_multi_instance_safety():
    """Test that multiple instances can run the send_event hook safely."""

    # Create a test transcript file
    test_transcript = Path("/tmp/test_transcript.jsonl")
    test_data = [{"role": "user", "content": f"Test message {i}"} for i in range(100)]

    with open(test_transcript, "w") as f:
        for item in test_data:
            f.write(json.dumps(item) + "\n")

    # Create test input data
    test_input = {"session_id": "test_session", "transcript_path": str(test_transcript)}

    # Function to run send_event hook
    def run_hook(instance_num):
        try:
            # Prepare input
            input_json = json.dumps(test_input)

            # Run the hook
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "--script",
                    ".claude/hooks/send_event.py",
                    "--source-app",
                    "test_app",
                    "--event-type",
                    "TestEvent",
                    "--add-chat",
                ],
                check=False,
                input=input_json,
                capture_output=True,
                text=True,
                timeout=10,
            )

            print(f"Instance {instance_num}: Exit code {result.returncode}")
            if result.stderr:
                print(f"Instance {instance_num} stderr: {result.stderr}")
            return result.returncode == 0
        except Exception as e:
            print(f"Instance {instance_num} failed: {e}")
            return False

    # Run multiple instances concurrently
    threads = []
    results = []

    print("Testing multi-instance safety with 5 concurrent instances...")

    for i in range(5):
        thread = threading.Thread(target=lambda x=i: results.append((x, run_hook(x))))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Check results
    successful = sum(1 for _, success in results if success)
    print(f"\nResults: {successful}/5 instances completed successfully")

    # Cleanup
    test_transcript.unlink(missing_ok=True)

    return successful == 5


if __name__ == "__main__":
    success = test_multi_instance_safety()
    sys.exit(0 if success else 1)
