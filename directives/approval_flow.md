# Directive: Approval Flow

## Goal
Present a preview of the post (media + caption + hashtags) to the user and require explicit approval before publishing to Instagram.

## Tool to Use
- **Script**: `execution/preview_post.py`

## Inputs
- `.tmp/caption.json` — Caption and hashtags generated
- `.tmp/media/image.png` or `.tmp/media/video.mp4` — Media to be posted

## Output
- `approved` → Proceed to `post_instagram.md`
- `rejected` + feedback → Return to `generate_content.md` or `generate_media.md` for adjustments

## Instructions

1. Call `execution/preview_post.py` to display the post preview in the terminal.
2. The preview must show:
   - 📸 Media path and thumbnail (if image)
   - 📝 Full caption with hashtags
   - 📊 Character count and hashtag count
3. Ask the user: **"Approve this post? [yes / no / edit caption / new image]"**
4. Route based on response:
   - **yes** → Save approval to `.tmp/approval.json`, proceed to posting
   - **no** → Discard and ask what to change
   - **edit caption** → Re-run `generate_content.md` with feedback
   - **new image** → Re-run `generate_media.md` with adjusted prompt

## Edge Cases
- Never proceed to posting without a confirmed `approved` status in `.tmp/approval.json`.
- If the user edits the caption manually, save the edited version to `.tmp/caption.json` before proceeding.
- Maximum 3 regeneration rounds before escalating to the user for manual input.

## Approval Record
Save approval metadata to `.tmp/approval.json`:
```json
{
  "approved": true,
  "approved_at": "2026-02-20T09:28:00-03:00",
  "caption_version": 1,
  "media_path": ".tmp/media/image.png"
}
```
