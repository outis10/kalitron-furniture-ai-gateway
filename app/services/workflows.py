"""ComfyUI workflow definitions for SDXL img2img and txt2img pipelines."""
from copy import deepcopy

STYLE_PROMPTS: dict[str, str] = {
    "modern": "kitchen interior design, modern minimalist style, handleless cabinets, quartz countertops, under-cabinet lighting, natural light",
    "classic": "kitchen interior design, classic traditional style, shaker cabinets, marble countertops, warm lighting, wood accents",
    "rustic": "kitchen interior design, rustic farmhouse style, open shelving, butcher block countertops, exposed beams, warm natural light",
    "industrial": "kitchen interior design, industrial loft style, concrete countertops, open metal shelving, Edison bulbs, dark palette",
    "scandinavian": "kitchen interior design, scandinavian style, white cabinets, light oak wood, clean lines, minimalist, bright natural light",
}

_PROMPT_SUFFIX = "professional photography, 8k, photorealistic, architectural visualization"
_NEGATIVE_PROMPT = "cartoon, illustration, low quality, blurry, watermark, text, signature, people, hands"

IMG2IMG_WORKFLOW: dict = {
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
    "5": {"class_type": "VAELoader", "inputs": {"vae_name": "sdxl_vae.safetensors"}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "PLACEHOLDER_POSITIVE"}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": _NEGATIVE_PROMPT}},
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
    "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": _NEGATIVE_PROMPT}},
    "8": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 768, "batch_size": 1}},
    "9": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["8", 0], "seed": 42, "steps": 35, "cfg": 7.5, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0}},
    "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["5", 0]}},
    "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "kalitron_txt2img"}},
}


def get_img2img_workflow(positive_prompt: str, image_filename: str) -> dict:
    """Return a ready-to-submit img2img workflow with prompts filled in."""
    workflow = deepcopy(IMG2IMG_WORKFLOW)
    style_prefix = "kitchen interior design, "
    full_prompt = f"{style_prefix}{positive_prompt}, {_PROMPT_SUFFIX}"
    workflow["6"]["inputs"]["text"] = full_prompt
    workflow["10"]["inputs"]["image"] = image_filename
    return workflow


def get_txt2img_workflow(positive_prompt: str, style: str = "modern") -> dict:
    """Return a ready-to-submit txt2img workflow with prompts filled in."""
    workflow = deepcopy(TXT2IMG_WORKFLOW)
    base = STYLE_PROMPTS.get(style, STYLE_PROMPTS["modern"])
    full_prompt = f"{base}, {positive_prompt}, {_PROMPT_SUFFIX}"
    workflow["6"]["inputs"]["text"] = full_prompt
    return workflow
