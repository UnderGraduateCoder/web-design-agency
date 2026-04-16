# Nano Banana 2 — Project Organizer

This document tracks progress, generated assets, and custom scripts for the Nano Banana 2 image generation project.

## Project Structure

Always keep prompts and images organized within the output directory.

- `output/assets/{client_slug}/` — All generated images, organized by client
- `output/prompts/{client_slug}/` — Saved JSON prompt configurations corresponding to generated images
- `tools/scripts/` — Utility scripts for API interaction and image generation
- `master_prompt_reference.md` — The compiled JSON schema and guide

## Image Generation Workflow

Whenever a user requests image generation using the Nano Banana 2 skill:

1. Build the prompt JSON using the Dense Narrative Format from `master_prompt_reference.md`
2. Save the prompt JSON to `output/prompts/{client_slug}/{image_name}.json`
3. Run `python tools/scripts/generate_kie.py output/prompts/{client_slug}/{image_name}.json output/assets/{client_slug}/{image_name}.jpg {aspect_ratio}`
4. Verify the image was saved successfully
5. **Parallel Processing:** When processing multiple images simultaneously, run generation commands in parallel to save time

## Scripts

| Script | Purpose | Status |
|---|---|---|
| `tools/scripts/generate_kie.py` | Hit Kie.ai API, poll for completion, download image | Active |
| `tools/scripts/get_kie_image.py` | Retrieve completed image by task ID | Active |

## API Parameters

- **Aspect ratios**: `16:9` (hero/landscape), `4:5` (card/portrait), `1:1` (square), `auto`
- **Resolution**: `1K` (default), `2K`, `4K`
- **Output format**: `jpg` (default), `png`
- **Model**: `nano-banana-2`
- **API endpoints**:
  - Create task: `POST https://api.kie.ai/api/v1/jobs/createTask`
  - Poll status: `GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId={id}`

## Fallback Chain

1. `KIE_API_KEY` + `tools/scripts/generate_kie.py` → Kie.ai Nano Banana 2
2. `GEMINI_API_KEY` + `tools/generate_images.py` → Gemini image generation
3. `STABILITY_API_KEY` + `tools/generate_images.py` → Stability AI
4. `placehold.co/{width}x{height}` — only if all API keys are missing
