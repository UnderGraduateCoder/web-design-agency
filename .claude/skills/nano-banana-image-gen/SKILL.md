---
name: nano-banana-image-gen
description: Generate hyper-realistic AI images via Kie.ai API using structured JSON prompting. Use when generating hero images, product shots, or any bespoke image via the nano-banana-2 model with KIE_API_KEY.
disable-model-invocation: true
---

# Nano Banana 2 Image Generation Master

A formalized skill for generating hyper-realistic, highly-controlled images using the Nano Banana 2 model through the Kie.ai API with parameterized JSON prompting.

## Goal

Provide a standardized, highly controlled method for generating images. By strictly enforcing a structured JSON parameter schema, this skill neutralizes native model biases (like over-smoothing, dataset-averaging, or "plastic" AI styling) and ensures raw, unretouched, hyper-realistic outputs.

## Prerequisites

- `KIE_API_KEY` set in `.env` at the project root
- A clear understanding of the desired Subject, Lighting, and Camera characteristics
- `tools/scripts/generate_kie.py` available for execution

## Core Schema — Dense Narrative Format (Use for Kie.ai)

When executing API calls to Kie.ai, condense all parameters into a dense, flat JSON string:

```json
{
  "prompt": "A dense, ultra-descriptive narrative. Use specific camera math (85mm lens, f/1.8, ISO 200), explicit flaws (visible pores, mild redness, subtle freckles), lighting behavior (golden hour raking light creating warm shadows), and direct negative commands (Do not beautify. No CGI. No studio lighting).",
  "negative_prompt": "blurry, low resolution, plastic skin, CGI, oversaturated, anatomy normalization, skin smoothing, airbrushed texture, stylized realism, editorial fashion proportions, beautification filters",
  "settings": {
    "resolution": "1K",
    "style": "photorealistic, documentary realism",
    "lighting": "natural golden hour, raking side light",
    "camera_angle": "eye level, 85mm lens",
    "depth_of_field": "shallow, f/1.8",
    "quality": "high detail, unretouched"
  },
  "api_parameters": {
    "aspect_ratio": "16:9",
    "resolution": "1K",
    "output_format": "jpg"
  }
}
```

For the full schema with object/nature details, multi-panel grids, and ControlNet parameters, see [master_prompt_reference.md](master_prompt_reference.md).

## Best Practices

1. **Camera Mathematics**: Always define exact focal length, aperture, and ISO (e.g., `85mm lens, f/2.0, ISO 200`). Forces optical physics rather than digital rendering.
2. **Explicit Imperfections**: "realistic" is not enough. Dictate flaws: mild redness, subtle freckles, light acne marks, unguided grooming.
3. **Direct Commands**: Use imperative negative commands *inside* the positive prompt: `Do not beautify or alter. No makeup styling.`
4. **Lighting Behavior**: Don't just name the light, name what it does: `direct flash creating sharp highlights on fabric and a slightly shadowed background`.
5. **Mandatory Negative Stack**: Always include explicit realism blockers — forbid "skin smoothing", "anatomy normalization", "plastic", "CGI".
6. **Avoid Over-Degradation (The Noise Trap)**: Keep ISO below 800. Heavy film grain in contrast-heavy environments triggers "digital art" biases. Use physical subject imperfections rather than camera noise to sell realism.
7. **Aspect Ratios**: `16:9` for hero/landscape, `4:5` for cards/portrait, `1:1` for square.

## Execution Workflow

### Step 1: Build the prompt JSON

Construct the Dense Narrative JSON using the format above. Save to `output/prompts/{client_slug}/{image_name}.json`.

For hero images:
- Subject: specific scene description with material/texture detail
- Lighting: golden hour / dramatic side lighting / etc.
- Camera: 85mm or wider for environment shots
- Style: photorealistic, documentary realism
- Negative: no CGI, no plastic, no studio lighting, no anatomy normalization

### Step 2: Create output directories

```
output/assets/{client_slug}/
output/prompts/{client_slug}/
```

### Step 3: Run the generation script

```bash
python tools/scripts/generate_kie.py \
  output/prompts/{client_slug}/{image_name}.json \
  output/assets/{client_slug}/{image_name}.jpg \
  16:9
```

The script will:
1. Read `KIE_API_KEY` from `.env`
2. POST to `https://api.kie.ai/api/v1/jobs/createTask`
3. Poll `recordInfo` every 4 seconds (up to 60 attempts)
4. Download and save the image when complete

### Step 4: Verify output

Check that `output/assets/{client_slug}/{image_name}.jpg` exists and has content. If the script fails with `KIE_API_KEY not found`, verify the `.env` file contains the key.

## Fallback Order

If `KIE_API_KEY` is not set, fall back in this order:
1. `GEMINI_API_KEY` → `tools/generate_images.py`
2. `STABILITY_API_KEY` → `tools/generate_images.py`
3. `placehold.co/{width}x{height}` — only if all API keys are missing

**Never use `placehold.co` if `KIE_API_KEY` is set.**

## Notes

- Do NOT run the script if KIE_API_KEY is not confirmed — check `.env` first
- Each generation costs API credits; confirm prompt is correct before running
- If the task fails on the server side, check `data.state` — may be `"failed"` or `"error"`
- For retrieving an existing completed task: `python tools/scripts/get_kie_image.py {taskId} {output_file}`
