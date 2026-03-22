"""
generate_catalog_images.py

Generates 4 catalog section images for the Mubetex website using Gemini (primary)
with Stability AI as fallback. Saves to output/assets/mubetex_catalog_*.jpg.
"""

import sys
import os
import base64
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("Error: 'requests' package not installed. Run: pip install requests")
    sys.exit(1)


CATALOG_IMAGES = [
    {
        "key": "moda",
        "filename": "mubetex_catalog_moda.jpg",
        "prompt": (
            "close-up macro photography of elegant fashion fabric swatches, "
            "silk and chiffon textiles draped with flowing folds, rich deep crimson and burgundy tones, "
            "soft studio lighting highlighting weave texture, luxurious fashion fabric, "
            "no text, no people, no watermarks, photorealistic, 4K"
        ),
    },
    {
        "key": "hogar",
        "filename": "mubetex_catalog_hogar.jpg",
        "prompt": (
            "close-up of premium home textile fabrics, warm beige and terracotta upholstery and curtain material, "
            "velvet and linen texture detail, cozy interior design aesthetic, "
            "soft warm lighting on fabric surface, elegant home decor textile, "
            "no text, no people, no watermarks, photorealistic, 4K"
        ),
    },
    {
        "key": "sostenible",
        "filename": "mubetex_catalog_sostenible.jpg",
        "prompt": (
            "sustainable organic fabric materials, natural undyed cotton and linen textile swatches, "
            "earthy green and natural cream tones, raw fiber texture, eco-friendly organic cotton weave, "
            "fresh botanical leaves alongside fabric samples, clean natural light, "
            "no text, no people, no watermarks, photorealistic, 4K"
        ),
    },
    {
        "key": "especial",
        "filename": "mubetex_catalog_especial.jpg",
        "prompt": (
            "premium technical fabric close-up, advanced performance textile with metallic thread detail, "
            "deep navy and silver fiber blend, intricate geometric weave pattern, "
            "dramatic side lighting revealing complex fabric structure, luxury high-performance textile, "
            "no text, no people, no watermarks, photorealistic, 4K"
        ),
    },
]

NEGATIVE_PROMPT = "text, watermarks, logos, people, faces, cartoonish, illustration, low quality, blurry, ugly"


def generate_with_gemini(prompt: str, output_path: Path) -> bool:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  GEMINI_API_KEY not set — falling back to Stability AI.")
        return False

    GEMINI_MODELS = [
        "gemini-2.0-flash-preview-image-generation",
        "gemini-2.0-flash-exp-image-generation",
    ]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    print(f"  Calling Gemini... prompt: {prompt[:70]}...")
    resp = None
    for model in GEMINI_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
        except requests.RequestException as e:
            print(f"  Gemini request failed: {e}")
            return False
        if resp.status_code != 404:
            break
        print(f"  Model {model} not available, trying next...")

    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp else "N/A"
        print(f"  Gemini HTTP {code} — falling back.")
        try:
            print(f"  Detail: {resp.json()}")
        except Exception:
            pass
        return False

    try:
        parts = resp.json()["candidates"][0]["content"]["parts"]
        image_part = next(p for p in parts if "inlineData" in p)
        image_bytes = base64.b64decode(image_part["inlineData"]["data"])
    except Exception as e:
        print(f"  Gemini parse error: {e} — falling back.")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)
    print(f"  Saved: {output_path} ({len(image_bytes)//1024} KB)")
    return True


def generate_with_stability(prompt: str, output_path: Path) -> bool:
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        print("  STABILITY_API_KEY not set — skipping.")
        return False

    url = "https://api.stability.ai/v2beta/stable-image/generate/core"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "image/*"}
    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "aspect_ratio": "3:2",
        "output_format": "jpeg",
    }

    print(f"  Calling Stability AI... prompt: {prompt[:70]}...")
    try:
        resp = requests.post(url, headers=headers, files={"none": ""}, data=payload, timeout=45)
    except requests.RequestException as e:
        print(f"  Stability AI request failed: {e}")
        return False

    if resp.status_code != 200:
        print(f"  Stability AI HTTP {resp.status_code}")
        try:
            print(f"  Detail: {resp.json()}")
        except Exception:
            print(f"  Body: {resp.text[:200]}")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(resp.content)
    print(f"  Saved: {output_path} ({len(resp.content)//1024} KB)")
    return True


def main():
    output_dir = Path("output/assets")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for item in CATALOG_IMAGES:
        key = item["key"]
        output_path = output_dir / item["filename"]

        if output_path.exists():
            print(f"[SKIP] {output_path.name} already exists.")
            results[key] = item["filename"]
            continue

        print(f"\n[{key.upper()}] Generating catalog image...")
        success = generate_with_gemini(item["prompt"], output_path)
        if not success:
            success = generate_with_stability(item["prompt"], output_path)

        if success:
            results[key] = item["filename"]
            print(f"  [OK] {item['filename']}")
        else:
            print(f"  [FAIL] Could not generate image for '{key}'.")

    print("\n--- Summary ---")
    for key, filename in results.items():
        print(f"  {key}: assets/{filename}")
    print("Done.")


if __name__ == "__main__":
    main()
