#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "openai",
# ]
# ///

import builtins
import contextlib
import os
import pathlib
import subprocess
import sys
import tempfile

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def main():
    """
    OpenAI TTS Script

    Uses OpenAI's TTS model for high-quality text-to-speech.
    Accepts optional text prompt as command-line argument.

    Usage:
    - ./openai_tts.py                    # Uses default text
    - ./openai_tts.py "Your custom text" # Uses provided text

    Features:
    - OpenAI tts-1 model
    - Alloy voice (default)
    - File-based playback for WSL compatibility
    """

    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        print("Please add your OpenAI API key to .env file:")
        print("OPENAI_API_KEY=your_api_key_here")
        sys.exit(1)

    try:
        import openai

        # Initialize OpenAI client
        client = openai.OpenAI(api_key=api_key)

        print("🎙️  OpenAI TTS")
        print("=" * 20)

        # Get text from command line argument or use default
        if len(sys.argv) > 1:
            text = " ".join(sys.argv[1:])  # Join all arguments as text
        else:
            text = "Today is a wonderful day to build something people love!"

        print(f"🎯 Text: {text}")
        print("🔊 Generating and playing...")

        try:
            # Generate audio
            response = client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
            )

            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(response.content)

            # Play the audio file using system commands
            for player in ["mpg123", "ffplay", "aplay", "paplay"]:
                try:
                    subprocess.run(
                        [player, temp_path],
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    break
                except (subprocess.SubprocessError, FileNotFoundError):
                    continue

            # Clean up temporary file
            with contextlib.suppress(builtins.BaseException):
                pathlib.Path(temp_path).unlink()

            print("✅ Playback complete!")

        except Exception as e:
            print(f"❌ Error: {e}")

    except ImportError:
        print("❌ Error: Required package not installed")
        print("This script uses UV to auto-install dependencies.")
        print("Make sure UV is installed: https://docs.astral.sh/uv/")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
