import os, torch
from helpers.training.state_tracker import StateTracker


def _model_imports(args):
    output = "import torch"
    output += f"from diffusers import DiffusionPipeline\n"


def _torch_device():
    return """'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'"""


def code_example(args):
    """Return a string with the code example."""
    code_example = f"""
```python
{_model_imports(args)}

model_id = "/path/to/checkpoint" # or "username/checkpoint"
prompt = "{args.validation_prompt if args.validation_prompt else 'An astronaut is riding a horse through the jungles of Thailand.'}"
negative_prompt = "malformed, disgusting, overexposed, washed-out"

pipeline = DiffusionPipeline.from_pretrained(model_id)
pipeline.to({_torch_device()})
image = pipeline(
    prompt=prompt,
    negative_prompt='{args.validation_negative_prompt}',
    num_inference_steps={args.validation_num_inference_steps},
    generator=torch.Generator(device={_torch_device()}).manual_seed(1641421826),
    width=1152,
    height=768,
    guidance_scale={args.validation_guidance},
    guidance_rescale={args.validation_guidance_rescale},
).images[0]
image.save(f"output.png", format="PNG")
```
"""
    return code_example


def lora_info(args):
    """Return a string with the LORA information."""
    if "lora" not in args.model_type:
        return ""
    return f"""- LoRA Rank: {args.lora_rank}
- LoRA Alpha: {args.lora_alpha}
- LoRA Dropout: {args.lora_dropout}
- LoRA initialisation style: {args.lora_init_type}
"""


def save_model_card(
    repo_id: str,
    images=None,
    base_model: str = "",
    train_text_encoder: bool = False,
    prompt: str = "",
    validation_prompts: dict = None,
    repo_folder: str = None,
):
    if repo_folder is None:
        raise ValueError("The repo_folder must be specified and not be None.")

    assets_folder = os.path.join(repo_folder, "assets")
    os.makedirs(assets_folder, exist_ok=True)
    datasets_str = ""
    for dataset in StateTracker.get_data_backends().keys():
        if "sampler" in StateTracker.get_data_backends()[dataset]:
            datasets_str += f"### {dataset}\n"
            datasets_str += f"{StateTracker.get_data_backends()[dataset]['sampler'].log_state(show_rank=False, alt_stats=True)}"
    widget_str = ""
    idx = 0
    shortname_idx = 0
    if images:
        widget_str = "widget:"
        for image_list in images.values() if isinstance(images, dict) else images:
            if not isinstance(image_list, list):
                image_list = [image_list]
            sub_idx = 0
            for image in image_list:
                image_path = os.path.join(assets_folder, f"image_{idx}_{sub_idx}.png")
                image.save(image_path, format="PNG")
                validation_prompt = "no prompt available"
                if validation_prompts is not None:
                    validation_prompt = validation_prompts.get(
                        shortname_idx, f"prompt not found ({shortname_idx})"
                    )
                if validation_prompt == "":
                    validation_prompt = "unconditional (blank prompt)"
                else:
                    # Escape anything that YAML won't like
                    validation_prompt = validation_prompt.replace("'", "''")
                widget_str += f"\n- text: '{validation_prompt}'"
                widget_str += f"\n  parameters:"
                widget_str += f"\n    negative_prompt: '{str(StateTracker.get_args().validation_negative_prompt)}'"
                widget_str += f"\n  output:"
                widget_str += f"\n    url: ./assets/image_{idx}_{sub_idx}.png"
                idx += 1
                sub_idx += 1

            shortname_idx += 1
    yaml_content = f"""---
license: creativeml-openrail-m
base_model: "{base_model}"
tags:
  - {'stable-diffusion' if 'deepfloyd' not in StateTracker.get_args().model_type else 'deepfloyd-if'}
  - {'stable-diffusion-diffusers' if 'deepfloyd' not in StateTracker.get_args().model_type else 'deepfloyd-if-diffusers'}
  - text-to-image
  - diffusers
  - {StateTracker.get_args().model_type}
{'  - template:sd-lora' if 'lora' in StateTracker.get_args().model_type else ''}
inference: true
{widget_str}
---

"""
    model_card_content = f"""# {repo_id}

This is a {'LoRA' if 'lora' in StateTracker.get_args().model_type else 'full rank finetune'} derived from [{base_model}](https://huggingface.co/{base_model}).

{'The main validation prompt used during training was:' if prompt else 'Validation used ground-truth images as an input for partial denoising (img2img).' if StateTracker.get_args().validation_using_datasets else 'No validation prompt was used during training.'}

{'```' if prompt else ''}
{prompt}
{'```' if prompt else ''}

## Validation settings
- CFG: `{StateTracker.get_args().validation_guidance}`
- CFG Rescale: `{StateTracker.get_args().validation_guidance_rescale}`
- Steps: `{StateTracker.get_args().validation_num_inference_steps}`
- Sampler: `{StateTracker.get_args().validation_noise_scheduler}`
- Seed: `{StateTracker.get_args().validation_seed}`
- Resolution{'s' if ',' in StateTracker.get_args().validation_resolution else ''}: `{StateTracker.get_args().validation_resolution}`

Note: The validation settings are not necessarily the same as the [training settings](#training-settings).

{'You can find some example images in the following gallery:' if images is not None else ''}\n

<Gallery />

The text encoder {'**was**' if train_text_encoder else '**was not**'} trained.
{'You may reuse the base model text encoder for inference.' if not train_text_encoder else 'If the text encoder from this repository is not used at inference time, unexpected or bad results could occur.'}


## Training settings

- Training epochs: {StateTracker.get_epoch() - 1}
- Training steps: {StateTracker.get_global_step()}
- Learning rate: {StateTracker.get_args().learning_rate}
- Effective batch size: {StateTracker.get_args().train_batch_size * StateTracker.get_args().gradient_accumulation_steps * StateTracker.get_accelerator().num_processes}
  - Micro-batch size: {StateTracker.get_args().train_batch_size}
  - Gradient accumulation steps: {StateTracker.get_args().gradient_accumulation_steps}
  - Number of GPUs: {StateTracker.get_accelerator().num_processes}
- Prediction type: {StateTracker.get_args().prediction_type}
- Rescaled betas zero SNR: {StateTracker.get_args().rescale_betas_zero_snr}
- Optimizer: {'AdamW, stochastic bf16' if StateTracker.get_args().adam_bfloat16 else 'AdamW8Bit' if StateTracker.get_args().use_8bit_adam else 'Adafactor' if StateTracker.get_args().use_adafactor_optimizer else 'Prodigy' if StateTracker.get_args().use_prodigy_optimizer else 'AdamW'}
- Precision: {'Pure BF16' if StateTracker.get_args().adam_bfloat16 else StateTracker.get_args().mixed_precision}
- Xformers: {'Enabled' if StateTracker.get_args().enable_xformers_memory_efficient_attention else 'Not used'}
{lora_info(args=StateTracker.get_args())}

## Datasets

{datasets_str}

## Inference

{code_example(StateTracker.get_args())}
"""

    print(f"YAML:\n{yaml_content}")
    print(f"Model Card:\n{model_card_content}")
    with open(os.path.join(repo_folder, "README.md"), "w") as f:
        f.write(yaml_content + model_card_content)
