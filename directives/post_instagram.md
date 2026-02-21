# Directive: Post to Instagram

## Goal
Publish the approved media and caption to Instagram using the Graph API. This step only runs after explicit approval in `approval_flow.md`.

## Pre-conditions
- `.tmp/approval.json` must exist and contain `"approved": true`
- `.tmp/caption.json` must contain `full_post` field
- `.tmp/media/image.png` or `.tmp/media/video.mp4` must exist

## Tool to Use
- **Script**: `execution/post_to_instagram.py`
- **API**: Instagram Graph API v21.0
- **Image hosting**: imgbb API (free) — required because Instagram Graph API only accepts public `image_url`, not direct file uploads

## Inputs (from .env)
- `INSTAGRAM_ACCESS_TOKEN` — Long-lived access token
- `INSTAGRAM_ACCOUNT_ID` — Instagram Business/Creator account ID
- `IMGBB_API_KEY` — Free API key from https://imgbb.com/signup (for public image hosting)

## Output
- Post URL: `https://www.instagram.com/p/{shortcode}/`
- Saved to: `.tmp/post_result.json`

## Instructions

### For Image Posts:
1. Verify approval in `.tmp/approval.json`.
2. Call `post_to_instagram.py` with `media_type=image`.
3. Script will:
   a. Upload image to `/{account_id}/media` endpoint with `image_url` or base64
   b. Retrieve `creation_id` from response
   c. Publish using `/{account_id}/media_publish` with the `creation_id`
4. Verify the response contains a valid post ID.
5. Save result to `.tmp/post_result.json`.

### For Video/Reel Posts:
1. Verify approval in `.tmp/approval.json`.
2. Call `post_to_instagram.py` with `media_type=reel`.
3. Script will:
   a. Upload video using resumable upload (container creation)
   b. Poll container status until `status_code` is `FINISHED`
   c. Publish using `/{account_id}/media_publish`
4. Video processing can take 1–5 minutes — wait and retry up to 10 times with 30s intervals.
5. Save result to `.tmp/post_result.json`.

## Edge Cases
- **Token expired**: Refresh the long-lived token. Long-lived tokens last 60 days. Add a reminder to `.env` with expiry date.
- **Media upload fails**: Check file size and format constraints (see `generate_media.md`).
- **Rate limit hit**: Instagram allows ~25 API calls/hour per token. Wait and retry.
- **Account not Business/Creator**: The publish API is not available for personal accounts. Inform the user.

## API Reference
- Container creation: `POST /{ig-user-id}/media`
- Publish: `POST /{ig-user-id}/media_publish`
- Docs: https://developers.facebook.com/docs/instagram-api/guides/content-publishing

## Post Result Format
```json
{
  "post_id": "17841234567890123",
  "post_url": "https://www.instagram.com/p/ABC123/",
  "published_at": "2026-02-20T09:30:00-03:00",
  "media_type": "image"
}
```
