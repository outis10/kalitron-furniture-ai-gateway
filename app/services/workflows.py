"""ComfyUI workflow definitions for SDXL img2img and txt2img pipelines."""
from copy import deepcopy

# ── Prompt constants ─────────────────────────────────────────────────────────

PROMPT_SUFFIX = "professional photography, 8k, photorealistic, architectural visualization"
NEGATIVE_PROMPT = "cartoon, illustration, low quality, blurry, watermark, text, signature, people, hands"

# ── Style templates ──────────────────────────────────────────────────────────

STYLE_PROMPTS: dict[str, str] = {
    "modern": "kitchen interior design, modern minimalist style, handleless cabinets, quartz countertops, under-cabinet lighting, natural light",
    "classic": "kitchen interior design, classic traditional style, shaker cabinets, marble countertops, warm lighting, wood accents",
    "rustic": "kitchen interior design, rustic farmhouse style, open shelving, butcher block countertops, exposed beams, warm natural light",
    "industrial": "kitchen interior design, industrial loft style, concrete countertops, open metal shelving, Edison bulbs, dark palette",
    "minimalist": "kitchen interior design, minimalist style, clean lines, hidden storage, integrated appliances, neutral palette, soft natural light",
}

CLOSET_STYLE_PROMPTS: dict[str, str] = {
    "modern": "wardrobe closet interior design, modern style, full-height cabinet doors, organized hanging space, drawers, shelves, soft natural light",
    "classic": "wardrobe closet interior design, classic built-in cabinetry, framed doors, elegant handles, organized hanging space, warm lighting",
    "rustic": "wardrobe closet interior design, rustic wood built-in wardrobe, natural grain texture, open shelving, warm inviting tones",
    "industrial": "wardrobe closet interior design, industrial built-in storage, dark metal accents, open shelves, drawers, matte finishes",
    "minimalist": "wardrobe closet interior design, minimalist built-in wardrobe, clean lines, flat doors, hidden storage, neutral palette, soft natural light",
}

BOTH_STYLE_PROMPTS: dict[str, str] = {
    key: f"{STYLE_PROMPTS[key]}, matching built-in wardrobe closet cabinetry"
    for key in STYLE_PROMPTS
}

PROJECT_STYLE_PROMPTS: dict[str, dict[str, str]] = {
    "KITCHEN": STYLE_PROMPTS,
    "CLOSET": CLOSET_STYLE_PROMPTS,
    "BOTH": BOTH_STYLE_PROMPTS,
}

# Maps Spanish (and English) style names to canonical STYLE_PROMPTS keys
STYLE_MAP: dict[str, str] = {
    "moderno": "modern",
    "modern": "modern",
    "rustico": "rustic",
    "rustic": "rustic",
    "minimalista": "minimalist",
    "minimalist": "minimalist",
    "clasico": "classic",
    "classic": "classic",
    "industrial": "industrial",
}

LAYOUT_DETAILS: dict[str, str] = {
    "l-shaped": "L-shaped kitchen layout with corner workspace and efficient storage",
    "en l": "L-shaped kitchen layout with corner workspace and efficient storage",
    "u-shaped": "U-shaped kitchen with wraparound countertops and ample cabinet space",
    "en u": "U-shaped kitchen with wraparound countertops and ample cabinet space",
    "galley": "galley kitchen with parallel countertops and streamlined workflow",
    "lineal": "galley kitchen with parallel countertops and streamlined workflow",
    "island": "open kitchen with central island, extra prep space and breakfast seating",
    "isla": "open kitchen with central island, extra prep space and breakfast seating",
}

CLOSET_LAYOUT_DETAILS: dict[str, str] = {
    "lineal": "linear built-in wardrobe spanning one wall",
    "linear": "linear built-in wardrobe spanning one wall",
    "l-shaped": "L-shaped closet storage wrapping around a corner",
    "en l": "L-shaped closet storage wrapping around a corner",
    "u-shaped": "U-shaped walk-in closet with storage on three sides",
    "en u": "U-shaped walk-in closet with storage on three sides",
    "walk-in": "walk-in closet with organized hanging rails, drawers and open shelves",
    "vestidor": "walk-in closet with organized hanging rails, drawers and open shelves",
}

FINISH_DETAILS: dict[str, str] = {
    "white matte": "white matte cabinet finish, clean bright surfaces, minimalist hardware",
    "blanco mate": "white matte cabinet finish, clean bright surfaces, minimalist hardware",
    "blanco opaco": "white matte cabinet finish, clean bright surfaces, minimalist hardware",
    "blanco brillante": "high gloss white finish, reflective clean bright surfaces, minimalist hardware",
    "alto brillo blanco": "high gloss white finish, reflective clean bright surfaces, minimalist hardware",
    "oak wood": "warm oak wood cabinet finish, natural grain texture, warm inviting tones",
    "madera roble": "warm oak wood cabinet finish, natural grain texture, warm inviting tones",
    "roble": "warm oak wood cabinet finish, natural grain texture, warm inviting tones",
    "gray matte": "gray matte cabinet finish, sophisticated neutral tone, modern hardware",
    "gris mate": "gray matte cabinet finish, sophisticated neutral tone, modern hardware",
    "gris opaco": "gray matte cabinet finish, sophisticated neutral tone, modern hardware",
    "black matte": "black matte cabinet finish, dramatic bold contrast, sleek statement",
    "negro mate": "black matte cabinet finish, dramatic bold contrast, sleek statement",
    "negro opaco": "black matte cabinet finish, dramatic bold contrast, sleek statement",
}

# ── ComfyUI Workflow JSON ────────────────────────────────────────────────────

IMG2IMG_WORKFLOW: dict = {
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
    "5": {"class_type": "VAELoader", "inputs": {"vae_name": "sdxl_vae.safetensors"}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "PLACEHOLDER_POSITIVE"}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": NEGATIVE_PROMPT}},
    "10": {"class_type": "LoadImage", "inputs": {"image": "PLACEHOLDER_IMAGE", "upload": "image"}},
    "11": {"class_type": "CannyEdgePreprocessor", "inputs": {"image": ["10", 0], "low_threshold": 100, "high_threshold": 200, "resolution": 1024}},
    "12": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": "controlnet-canny-sdxl-1.0.safetensors"}},
    "13": {"class_type": "ControlNetApplyAdvanced", "inputs": {"positive": ["6", 0], "negative": ["7", 0], "control_net": ["12", 0], "image": ["11", 0], "strength": 0.75, "start_percent": 0.0, "end_percent": 1.0}},
    "14": {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["5", 0]}},
    "15": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["13", 0], "negative": ["13", 1], "latent_image": ["14", 0], "seed": 42, "steps": 30, "cfg": 7.0, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 0.75}},
    "16": {"class_type": "VAEDecode", "inputs": {"samples": ["15", 0], "vae": ["5", 0]}},
    "17": {"class_type": "SaveImage", "inputs": {"images": ["16", 0], "filename_prefix": "kalitron_img2img"}},
}

TXT2IMG_WORKFLOW: dict = {
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
    "5": {"class_type": "VAELoader", "inputs": {"vae_name": "sdxl_vae.safetensors"}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "PLACEHOLDER_POSITIVE"}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": NEGATIVE_PROMPT}},
    "8": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 768, "batch_size": 1}},
    "9": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["8", 0], "seed": 42, "steps": 35, "cfg": 7.5, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0}},
    "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["5", 0]}},
    "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "kalitron_txt2img"}},
}


def get_img2img_workflow(full_positive_prompt: str, image_filename: str) -> dict:
    """Return a ready-to-submit img2img workflow. full_positive_prompt is used as-is."""
    workflow = deepcopy(IMG2IMG_WORKFLOW)
    workflow["6"]["inputs"]["text"] = full_positive_prompt
    workflow["10"]["inputs"]["image"] = image_filename
    return workflow


def get_txt2img_workflow(full_positive_prompt: str) -> dict:
    """Return a ready-to-submit txt2img workflow. full_positive_prompt is used as-is."""
    workflow = deepcopy(TXT2IMG_WORKFLOW)
    workflow["6"]["inputs"]["text"] = full_positive_prompt
    return workflow
