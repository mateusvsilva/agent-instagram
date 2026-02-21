# Directive: Generate Media (Image or Video)

## Goal
Generate or process visual media (image or video) to accompany the Instagram post.

## Inputs
- `prompt` (str): A descriptive prompt for image generation, derived from the user's message (e.g., "Flat lay of artisanal coffee cup with award ribbon, warm tones, professional photography style")
- `media_type` (str): `image` (default) or `video`
- `user_provided_path` (str, optional): If the user provides their own image/video, its local path

## Tool to Use
- **Script**: `execution/generate_image.py`
- **AI Provider**: Gemini Imagen API (primary) or DALL-E 3 via OpenAI (fallback)
- For **video**: User must provide the video file (automated generation not yet supported)

## Output
- Image: `.tmp/media/image.png`
- Video: `.tmp/media/video.mp4` (user-provided copy)

## Instructions

### If generating an image:
1. Derive a visual prompt from the user's message and generated caption.
2. The prompt should describe: subject, style, lighting, mood, composition.
3. Call `execution/generate_image.py` with the derived prompt.
4. Verify the output image exists and is valid (min 500x500px for Instagram).
5. Save to `.tmp/media/image.png`.

### If user provides media:
1. Copy the file to `.tmp/media/` with the appropriate name.
2. Validate format:
   - Image: JPG, PNG — min 320x320px, max 8MB
   - Video: MP4 — min 3s, max 60s for Reels, max 1GB

## Edge Cases
- If the generated image does not match the post theme, refine the prompt with more specific visual descriptors and retry.
- If the image generation API fails, ask the user to provide an image manually.
- Always prefer square (1:1) or portrait (4:5) aspect ratios for better Instagram reach.

## Notes
- Update this directive if Gemini Imagen adds video generation support.
- Video posting requires a different API flow (container upload) — follow `post_instagram.md`.
