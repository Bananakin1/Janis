#!/usr/bin/env python
"""Smoke test for Janis - tests against real Azure OpenAI and Obsidian.

This script bypasses Discord and tests the orchestrator directly against
real services. It creates a meeting note and verifies the output.

Usage:
    python scripts/smoke_test.py

Requirements:
    - .env file with valid credentials
    - Obsidian running with REST API enabled
    - Azure OpenAI deployment accessible

Note: This test does NOT clean up after itself. The created note
remains in the vault for manual inspection. Delete it manually before
re-running.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.agent.orchestrator import Orchestrator
from src.obsidian.vault_index import VaultIndex


# =============================================================================
# TEST CONFIGURATION - Static values for reproducible tests
# =============================================================================

TEST_NOTE_NAME = "Jacob Lee"
TEST_FOLDER = "Meetings"
EXPECTED_HUB_LINK = "[[MEETINGS]]"

TEST_MESSAGE = """Create a new note for today's meeting with Jacob Lee with the following bullet points:
- Discussed Q1 roadmap priorities and timeline adjustments
- Agreed to mass hire 20 engineers for Centring team by March
- Need to finalize budget proposal for board presentation
- Action item: Jacob to send partnership agreement draft by Friday"""

# Keywords from bullet points that MUST appear in the created note
REQUIRED_KEYWORDS = [
    "roadmap",
    "engineers",
    "budget",
    "partnership",
]


# =============================================================================
# TEST IMPLEMENTATION
# =============================================================================

class SmokeTestError(Exception):
    """Raised when a smoke test assertion fails."""
    pass


def get_expected_date() -> str:
    """Get today's date in the expected format (MM/DD/YYYY)."""
    return datetime.now().strftime("%m/%d/%Y")


def check_note_does_not_exist(vault_index: VaultIndex, note_name: str) -> None:
    """Verify the test note doesn't already exist."""
    vault_index.refresh()

    if vault_index.note_exists(note_name):
        note_path = vault_index.get_note_path(note_name)
        raise SmokeTestError(
            f"\n{'='*60}\n"
            f"SMOKE TEST BLOCKED: Note already exists!\n"
            f"{'='*60}\n\n"
            f"The note '{note_name}' already exists in your vault.\n"
            f"Location: {note_path}\n\n"
            f"This smoke test requires a clean state to verify note creation.\n\n"
            f"To fix:\n"
            f"  1. Manually delete the note from your vault\n"
            f"  2. Re-run this smoke test\n\n"
            f"The note is NOT auto-deleted to preserve your data.\n"
            f"{'='*60}"
        )


def verify_note_created(vault_index: VaultIndex, note_name: str, folder: str) -> Path:
    """Verify the note was created in the correct location."""
    vault_index.refresh()

    if not vault_index.note_exists(note_name):
        raise SmokeTestError(
            f"Note '{note_name}' was not created. "
            f"Check the orchestrator response for errors."
        )

    note_path = vault_index.get_note_path(note_name)
    if note_path is None:
        raise SmokeTestError(f"Note exists but path could not be resolved.")

    # Normalize to string for comparison
    path_str = str(note_path).replace("\\", "/")
    if f"{folder}/" not in path_str:
        raise SmokeTestError(
            f"Note created in wrong folder.\n"
            f"Expected: {folder}/\n"
            f"Actual path: {note_path}"
        )

    return note_path


def verify_note_content(
    note_path: Path,
    vault_path: Path,
    expected_date: str,
    hub_link: str,
    keywords: list[str],
) -> None:
    """Verify the note content meets all requirements."""
    # Read the actual file
    full_path = vault_path / note_path
    if not full_path.exists():
        # Try with .md extension
        full_path = vault_path / f"{note_path}.md" if not str(note_path).endswith('.md') else full_path

    if not full_path.exists():
        raise SmokeTestError(f"Note file not found at: {full_path}")

    content = full_path.read_text(encoding="utf-8")
    errors = []

    # Check date format (MM/DD/YYYY)
    if expected_date not in content:
        errors.append(
            f"Date not found in expected format.\n"
            f"  Expected: {expected_date}\n"
            f"  Note content does not contain this date."
        )

    # Check hub wikilink
    if hub_link not in content:
        errors.append(
            f"Hub link not found.\n"
            f"  Expected: {hub_link}\n"
            f"  This should appear in the frontmatter."
        )

    # Check keywords from bullet points
    content_lower = content.lower()
    missing_keywords = [kw for kw in keywords if kw.lower() not in content_lower]
    if missing_keywords:
        errors.append(
            f"Missing keywords from bullet points.\n"
            f"  Expected keywords: {keywords}\n"
            f"  Missing: {missing_keywords}"
        )

    if errors:
        error_details = "\n\n".join(f"[{i+1}] {e}" for i, e in enumerate(errors))
        raise SmokeTestError(
            f"\n{'='*60}\n"
            f"CONTENT VERIFICATION FAILED\n"
            f"{'='*60}\n\n"
            f"{error_details}\n\n"
            f"{'='*60}\n"
            f"ACTUAL NOTE CONTENT:\n"
            f"{'='*60}\n"
            f"{content}\n"
            f"{'='*60}"
        )


async def run_smoke_test() -> None:
    """Run the smoke test against real services."""
    print("=" * 60)
    print("JANIS SMOKE TEST")
    print("=" * 60)
    print()

    # Load settings
    print("[1/6] Loading settings from .env...")
    try:
        settings = get_settings()
        print(f"      Vault: {settings.obsidian_vault_path}")
        print(f"      Azure endpoint: {settings.azure_openai_endpoint}")
        print(f"      Deployment: {settings.azure_openai_deployment}")
    except Exception as e:
        raise SmokeTestError(f"Failed to load settings: {e}")

    # Initialize components
    print("\n[2/6] Initializing orchestrator and vault index...")
    orchestrator = Orchestrator(settings)
    vault_index = VaultIndex(settings.obsidian_vault_path)

    # Pre-flight check: note should not exist
    print(f"\n[3/6] Checking '{TEST_NOTE_NAME}' does not already exist...")
    check_note_does_not_exist(vault_index, TEST_NOTE_NAME)
    print("      OK - Note does not exist")

    # Run the test message through orchestrator
    print(f"\n[4/6] Sending test message to orchestrator...")
    print(f"      Message: {TEST_MESSAGE[:60]}...")

    try:
        response = await orchestrator.process_message(TEST_MESSAGE)
        print(f"\n      Response: {response}")
    except Exception as e:
        raise SmokeTestError(f"Orchestrator failed: {e}")

    # Verify note was created in correct location
    print(f"\n[5/6] Verifying note created in {TEST_FOLDER}/...")
    note_path = verify_note_created(vault_index, TEST_NOTE_NAME, TEST_FOLDER)
    print(f"      OK - Note created at: {note_path}")

    # Verify note content
    print("\n[6/6] Verifying note content...")
    expected_date = get_expected_date()
    print(f"      Checking date format: {expected_date}")
    print(f"      Checking hub link: {EXPECTED_HUB_LINK}")
    print(f"      Checking keywords: {REQUIRED_KEYWORDS}")

    verify_note_content(
        note_path=note_path,
        vault_path=settings.obsidian_vault_path,
        expected_date=expected_date,
        hub_link=EXPECTED_HUB_LINK,
        keywords=REQUIRED_KEYWORDS,
    )
    print("      OK - All content checks passed")

    # Success
    print()
    print("=" * 60)
    print("SMOKE TEST PASSED")
    print("=" * 60)
    print()
    print(f"Note created: {settings.obsidian_vault_path / note_path}")
    print()
    print("Remember to manually delete this note before re-running.")
    print()


def main() -> int:
    """Entry point."""
    try:
        asyncio.run(run_smoke_test())
        return 0
    except SmokeTestError as e:
        print(f"\nSMOKE TEST FAILED:\n{e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
