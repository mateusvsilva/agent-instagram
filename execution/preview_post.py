"""
preview_post.py
---------------
Layer 3 — Execution Script

Displays a preview of the post (media + caption) in the terminal and
prompts the user for approval before publishing.

Usage:
    python execution/preview_post.py

Reads:
    .tmp/caption.json
    .tmp/media/image.png  (or video.mp4)

Output:
    .tmp/approval.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

console = Console()

CAPTION_PATH = Path(".tmp/caption.json")
IMAGE_PATH = Path(".tmp/media/image.png")
VIDEO_PATH = Path(".tmp/media/video.mp4")
APPROVAL_PATH = Path(".tmp/approval.json")


def load_caption() -> dict:
    if not CAPTION_PATH.exists():
        console.print(f"[red]❌ Caption file not found: {CAPTION_PATH}[/red]")
        console.print("[yellow]Run generate_caption.py first.[/yellow]")
        sys.exit(1)
    return json.loads(CAPTION_PATH.read_text(encoding="utf-8"))


def find_media() -> tuple[Path | None, str]:
    """Return (media_path, media_type) or (None, '')."""
    if IMAGE_PATH.exists():
        return IMAGE_PATH, "image"
    if VIDEO_PATH.exists():
        return VIDEO_PATH, "video"
    return None, ""


def display_preview(caption_data: dict, media_path: Path | None, media_type: str):
    """Render a styled post preview in the terminal."""
    console.rule("[bold blue]📸 Instagram Post Preview[/bold blue]")

    # Media info
    if media_path:
        size_mb = media_path.stat().st_size / (1024 * 1024)
        console.print(
            Panel(
                f"[bold]{media_type.upper()}[/bold]: {media_path}\n"
                f"Size: {size_mb:.2f} MB",
                title="🖼  Media",
                border_style="cyan",
            )
        )
    else:
        console.print(Panel("[red]⚠️  No media found in .tmp/media/[/red]", title="Media", border_style="red"))

    # Caption
    caption = caption_data.get("caption", "")
    hashtags = caption_data.get("hashtags", "")
    full_post = caption_data.get("full_post", caption + "\n\n" + hashtags)

    char_count = len(full_post)
    hashtag_count = len(hashtags.split())

    caption_text = Text()
    caption_text.append(caption + "\n\n", style="white")
    caption_text.append(hashtags, style="bold blue")

    console.print(
        Panel(
            caption_text,
            title=f"📝 Caption ({char_count} chars, {hashtag_count} hashtags)",
            border_style="green",
        )
    )

    console.rule()


def save_approval(approved: bool, media_path: Path | None, version: int = 1):
    APPROVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "approved": approved,
        "approved_at": datetime.now().astimezone().isoformat(),
        "caption_version": version,
        "media_path": str(media_path) if media_path else None,
    }
    APPROVAL_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    caption_data = load_caption()
    media_path, media_type = find_media()

    display_preview(caption_data, media_path, media_type)

    console.print("\n[bold]What would you like to do?[/bold]")
    console.print("  [green]yes[/green]          → Approve and publish")
    console.print("  [red]no[/red]           → Reject (abort)")
    console.print("  [yellow]edit caption[/yellow] → Re-generate caption")
    console.print("  [yellow]new image[/yellow]    → Re-generate image\n")

    choice = Prompt.ask(
        "[bold cyan]Your decision[/bold cyan]",
        choices=["yes", "no", "edit caption", "new image"],
        default="yes",
    )

    if choice == "yes":
        save_approval(approved=True, media_path=media_path)
        console.print("\n[bold green]✅ Approved! Proceeding to publish...[/bold green]")
        sys.exit(0)

    elif choice == "no":
        save_approval(approved=False, media_path=media_path)
        console.print("\n[bold red]❌ Post rejected. No changes made.[/bold red]")
        sys.exit(1)

    elif choice == "edit caption":
        feedback = Prompt.ask("[yellow]What should be changed in the caption?[/yellow]")
        # Save feedback so the orchestrator can re-run generate_caption.py with it
        feedback_path = Path(".tmp/caption_feedback.txt")
        feedback_path.write_text(feedback, encoding="utf-8")
        console.print(f"[yellow]Feedback saved to {feedback_path}. Re-run generate_caption.py.[/yellow]")
        sys.exit(2)

    elif choice == "new image":
        feedback = Prompt.ask("[yellow]Describe the new image you want[/yellow]")
        feedback_path = Path(".tmp/image_feedback.txt")
        feedback_path.write_text(feedback, encoding="utf-8")
        console.print(f"[yellow]Feedback saved to {feedback_path}. Re-run generate_image.py.[/yellow]")
        sys.exit(3)


if __name__ == "__main__":
    main()
