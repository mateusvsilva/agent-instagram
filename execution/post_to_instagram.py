"""
post_to_instagram.py
---------------------
Layer 3 — Execution Script

Publishes an approved post to Instagram using the Graph API.
Only runs after preview_post.py saves .tmp/approval.json with approved=true.

Usage:
    python execution/post_to_instagram.py [--media-type image|reel]

Reads:
    .tmp/approval.json
    .tmp/caption.json
    .tmp/media/image.png  or  .tmp/media/video.mp4

Output:
    .tmp/post_result.json
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

# ─── Config ───────────────────────────────────────────────────────────────────
GRAPH_API_BASE = "https://graph.facebook.com/v21.0"
APPROVAL_PATH = Path(".tmp/approval.json")
CAPTION_PATH = Path(".tmp/caption.json")
IMAGE_PATH = Path(".tmp/media/image.png")
VIDEO_PATH = Path(".tmp/media/video.mp4")
RESULT_PATH = Path(".tmp/post_result.json")

# Max retries for video processing status check
VIDEO_STATUS_RETRIES = 10
VIDEO_STATUS_INTERVAL = 30  # seconds
IMAGE_STATUS_RETRIES = 12
IMAGE_STATUS_INTERVAL = 5  # seconds
PUBLISH_RETRIES = 3
PUBLISH_RETRY_INTERVAL = 10  # seconds


def get_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        console.print(f"[red]❌ Missing environment variable: {key}[/red]")
        console.print(f"[yellow]Add it to your .env file. See .env.example[/yellow]")
        sys.exit(1)
    return value


def check_approval() -> dict:
    """Verify that an explicit approval exists."""
    if not APPROVAL_PATH.exists():
        console.print("[red]❌ No approval file found. Run preview_post.py first.[/red]")
        sys.exit(1)

    approval = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    if not approval.get("approved"):
        console.print("[red]❌ Post was not approved. Aborting.[/red]")
        sys.exit(1)

    return approval


def load_caption() -> str:
    """Load the full post text (caption + hashtags)."""
    if not CAPTION_PATH.exists():
        console.print("[red]❌ Caption file not found.[/red]")
        sys.exit(1)
    data = json.loads(CAPTION_PATH.read_text(encoding="utf-8"))
    return data.get("full_post") or data.get("caption", "")


def _parse_response_json(response: requests.Response) -> dict | None:
    try:
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except ValueError:
        return None


def log_graph_api_error(response: requests.Response, action: str) -> None:
    """Print a structured Graph API error so failures are diagnosable."""
    console.print(
        f"[red]❌ Instagram API error while {action}: HTTP {response.status_code}[/red]"
    )
    payload = _parse_response_json(response)
    if not payload:
        console.print(f"[red]{response.text}[/red]")
        return

    error = payload.get("error")
    if not isinstance(error, dict):
        console.print(f"[red]{payload}[/red]")
        return

    message = error.get("message")
    code = error.get("code")
    subcode = error.get("error_subcode")
    user_title = error.get("error_user_title")
    user_msg = error.get("error_user_msg")
    trace = error.get("fbtrace_id")

    if message:
        console.print(f"[red]message:[/red] {message}")
    if code is not None:
        console.print(f"[red]code:[/red] {code}")
    if subcode is not None:
        console.print(f"[red]subcode:[/red] {subcode}")
    if user_title:
        console.print(f"[red]user_title:[/red] {user_title}")
    if user_msg:
        console.print(f"[red]user_message:[/red] {user_msg}")
    if trace:
        console.print(f"[red]fbtrace_id:[/red] {trace}")


def is_transient_not_ready_error(response: requests.Response) -> bool:
    payload = _parse_response_json(response)
    if not payload:
        return False

    error = payload.get("error")
    if not isinstance(error, dict):
        return False

    message = str(error.get("message", "")).lower()
    user_message = str(error.get("error_user_msg", "")).lower()
    combined = f"{message} {user_message}"
    markers = ("not ready", "not available", "is still processing", "try again")
    return any(marker in combined for marker in markers)


def upload_to_imgbb(image_path: Path) -> str:
    """
    Upload image to imgbb and return a public URL.
    Instagram Graph API requires a publicly accessible image_url.
    imgbb free tier: https://api.imgbb.com/
    Set IMGBB_API_KEY in .env (free at https://imgbb.com/signup)
    """
    api_key = os.getenv("IMGBB_API_KEY")
    if not api_key:
        console.print("[red]❌ IMGBB_API_KEY not set in .env[/red]")
        console.print("[yellow]Get a free key at https://imgbb.com/signup then add IMGBB_API_KEY=... to .env[/yellow]")
        sys.exit(1)

    console.print("[cyan]☁️  Hosting image publicly via imgbb...[/cyan]")

    with open(image_path, "rb") as f:
        import base64
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": api_key, "image": image_b64},
        timeout=60,
    )

    if not response.ok:
        console.print(f"[red]❌ imgbb upload failed: {response.status_code} {response.text}[/red]")
        sys.exit(1)

    result = response.json()
    public_url = result["data"]["url"]
    console.print(f"[green]✓ Image hosted at: {public_url}[/green]")
    return public_url


def upload_image(account_id: str, token: str, caption: str) -> str:
    """Upload image to Instagram and return creation_id.
    
    Instagram Graph API requires image_url to be a publicly accessible URL.
    We first upload the image to imgbb, then pass the URL to the Graph API.
    """
    if not IMAGE_PATH.exists():
        console.print(f"[red]❌ Image not found at {IMAGE_PATH}[/red]")
        sys.exit(1)

    console.print(f"[cyan]📤 Uploading image to Instagram...[/cyan]")

    # Step 1: Get a public URL for the image
    public_url = upload_to_imgbb(IMAGE_PATH)

    # Step 2: Create Instagram media container using the public URL
    url = f"{GRAPH_API_BASE}/{account_id}/media"
    data = {
        "image_url": public_url,
        "caption": caption,
        "access_token": token,
    }

    response = requests.post(url, data=data, timeout=60)

    if not response.ok:
        log_graph_api_error(response, "creating image media container")
        response.raise_for_status()

    result = response.json()
    creation_id = result.get("id")
    if not creation_id:
        console.print(f"[red]❌ Failed to create media container: {result}[/red]")
        sys.exit(1)

    console.print(f"[green]✓ Media container created: {creation_id}[/green]")
    return creation_id


def upload_video_reel(account_id: str, token: str, caption: str) -> str:
    """Upload video as Reel and return creation_id."""

    if not VIDEO_PATH.exists():
        console.print(f"[red]❌ Video not found at {VIDEO_PATH}[/red]")
        sys.exit(1)

    file_size = VIDEO_PATH.stat().st_size
    console.print(f"[cyan]📤 Uploading video ({file_size / 1024 / 1024:.1f} MB)...[/cyan]")

    # Step 1: Initialize upload session
    init_url = f"{GRAPH_API_BASE}/{account_id}/media"
    init_data = {
        "media_type": "REELS",
        "caption": caption,
        "access_token": token,
        "upload_type": "resumable",
    }

    init_resp = requests.post(init_url, data=init_data, timeout=30)
    init_resp.raise_for_status()
    container_id = init_resp.json().get("id")

    if not container_id:
        console.print(f"[red]❌ Failed to initialize upload: {init_resp.json()}[/red]")
        sys.exit(1)

    # Step 2: Upload video bytes
    video_url = f"https://rupload.facebook.com/video-upload/v21.0/{container_id}"
    headers = {
        "Authorization": f"OAuth {token}",
        "offset": "0",
        "file_size": str(file_size),
        "Content-Type": "application/octet-stream",
    }

    with open(VIDEO_PATH, "rb") as f:
        upload_resp = requests.post(video_url, headers=headers, data=f, timeout=300)
    upload_resp.raise_for_status()

    console.print(f"[green]✓ Video uploaded. Container: {container_id}[/green]")

    # Step 3: Poll for processing status
    console.print("[cyan]⏳ Waiting for video processing...[/cyan]")
    for attempt in range(VIDEO_STATUS_RETRIES):
        status_resp = requests.get(
            f"{GRAPH_API_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=15,
        )
        status_resp.raise_for_status()
        status = status_resp.json().get("status_code")

        console.print(f"[grey50]  Status ({attempt + 1}/{VIDEO_STATUS_RETRIES}): {status}[/grey50]")

        if status == "FINISHED":
            break
        elif status == "ERROR":
            console.print("[red]❌ Video processing failed.[/red]")
            sys.exit(1)

        time.sleep(VIDEO_STATUS_INTERVAL)
    else:
        console.print("[red]❌ Video processing timed out.[/red]")
        sys.exit(1)

    return container_id


def wait_for_container_ready(container_id: str, token: str) -> None:
    """Wait for an image container to finish processing before publish."""
    console.print("[cyan]⏳ Waiting for media container to be ready...[/cyan]")
    for attempt in range(IMAGE_STATUS_RETRIES):
        status_resp = requests.get(
            f"{GRAPH_API_BASE}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=15,
        )

        if not status_resp.ok:
            log_graph_api_error(status_resp, "checking media container status")
            console.print(
                "[yellow]Proceeding to publish anyway because status could not be read.[/yellow]"
            )
            return

        payload = _parse_response_json(status_resp) or {}
        status = payload.get("status_code") or payload.get("status")
        console.print(
            f"[grey50]  Status ({attempt + 1}/{IMAGE_STATUS_RETRIES}): {status}[/grey50]"
        )

        if status in (None, ""):
            return
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED"}:
            console.print(f"[red]❌ Media container failed with status: {status}[/red]")
            console.print(f"[red]{payload}[/red]")
            sys.exit(1)

        time.sleep(IMAGE_STATUS_INTERVAL)

    console.print(
        "[yellow]Media container was not FINISHED before timeout; attempting publish anyway.[/yellow]"
    )


def publish_media(account_id: str, token: str, creation_id: str) -> dict:
    """Publish the media container and return post result."""
    console.print("[cyan]🚀 Publishing post...[/cyan]")

    url = f"{GRAPH_API_BASE}/{account_id}/media_publish"
    data = {
        "creation_id": creation_id,
        "access_token": token,
    }

    for attempt in range(PUBLISH_RETRIES):
        response = requests.post(url, data=data, timeout=30)
        if response.ok:
            return response.json()

        if attempt < PUBLISH_RETRIES - 1 and is_transient_not_ready_error(response):
            wait_seconds = PUBLISH_RETRY_INTERVAL * (attempt + 1)
            console.print(
                f"[yellow]Media not ready yet. Retrying publish in {wait_seconds}s...[/yellow]"
            )
            time.sleep(wait_seconds)
            continue

        log_graph_api_error(response, "publishing media")
        response.raise_for_status()

    raise RuntimeError("Publishing failed after retries.")


def main():
    parser = argparse.ArgumentParser(description="Publish post to Instagram")
    parser.add_argument(
        "--media-type",
        choices=["image", "reel"],
        default="image",
        help="Type of media to post",
    )
    args = parser.parse_args()

    # Load credentials
    token = get_env("INSTAGRAM_ACCESS_TOKEN")
    account_id = get_env("INSTAGRAM_ACCOUNT_ID")

    # Gate: approval check
    approval = check_approval()
    console.print(f"[green]✓ Approval verified (approved at {approval['approved_at']})[/green]")

    # Load caption
    caption = load_caption()
    console.print(f"[grey50]Caption ({len(caption)} chars): {caption[:60]}...[/grey50]")

    # Upload media
    if args.media_type == "image":
        creation_id = upload_image(account_id, token, caption)
        wait_for_container_ready(creation_id, token)
    else:
        creation_id = upload_video_reel(account_id, token, caption)

    # Publish
    publish_result = publish_media(account_id, token, creation_id)
    post_id = publish_result.get("id")

    if not post_id:
        console.print(f"[red]❌ Publishing failed: {publish_result}[/red]")
        sys.exit(1)

    # Save result
    result = {
        "post_id": post_id,
        "post_url": f"https://www.instagram.com/p/{post_id}/",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "media_type": args.media_type,
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    console.print(f"\n[bold green]🎉 Post published successfully![/bold green]")
    console.print(f"[bold]Post ID:[/bold] {post_id}")
    console.print(f"[bold]Result saved to:[/bold] {RESULT_PATH}")


if __name__ == "__main__":
    main()
