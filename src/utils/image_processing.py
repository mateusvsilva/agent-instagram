from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image

from ..domain.models.post import ValidationResult
from ..utils.logger import get_logger

logger = get_logger(__name__)

INSTAGRAM_CAROUSEL_WIDTH = 1080
INSTAGRAM_CAROUSEL_HEIGHT = 1350
MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024
MIN_ASPECT_RATIO = 4 / 5
MAX_ASPECT_RATIO = 1.91

# Instagram aceita posts de 1 (imagem única) a 10 (carrossel) imagens.
MIN_CAROUSEL_IMAGES = 1
MAX_CAROUSEL_IMAGES = 10

_LOGO_POSITIONS = {"bottom-right", "bottom-left", "top-right", "top-left"}


@dataclass(frozen=True)
class LogoOverlay:
    """Configuração para sobrepor o logo real por cima da imagem gerada."""

    path: Path
    position: str = "bottom-right"
    scale: float = 0.18  # largura do logo como fração da largura da imagem
    margin: int = 48  # px da borda
    opacity: float = 0.9  # 0.0 (transparente) … 1.0 (opaco)


def resize_for_instagram(
    image_path: Path, output_path: Path, logo: Optional[LogoOverlay] = None
) -> Path:
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        img = _fit_to_canvas(img, INSTAGRAM_CAROUSEL_WIDTH, INSTAGRAM_CAROUSEL_HEIGHT)
        if logo is not None:
            img = apply_logo(img, logo)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format="JPEG", quality=92, optimize=True)
    return output_path


def apply_logo(canvas: Image.Image, logo: LogoOverlay) -> Image.Image:
    """Cola o logo (PNG com transparência) sobre `canvas`.

    Falhas (arquivo ausente, posição inválida, imagem corrompida) são logadas e
    ignoradas — o overlay do logo nunca deve quebrar a publicação de um post.
    """
    if not logo.path.exists():
        logger.warning("Logo habilitado, mas arquivo não encontrado: %s — pulando overlay.", logo.path)
        return canvas
    if logo.position not in _LOGO_POSITIONS:
        logger.warning("Posição de logo inválida '%s' — usando 'bottom-right'.", logo.position)
        position = "bottom-right"
    else:
        position = logo.position

    try:
        with Image.open(logo.path) as raw:
            mark = raw.convert("RGBA")
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("Não foi possível abrir o logo %s: %s — pulando overlay.", logo.path, exc)
        return canvas

    target_w = max(1, int(canvas.width * logo.scale))
    ratio = target_w / mark.width
    target_h = max(1, int(mark.height * ratio))
    mark = mark.resize((target_w, target_h), Image.LANCZOS)

    if logo.opacity < 1.0:
        alpha = mark.getchannel("A").point(lambda a: int(a * max(0.0, min(1.0, logo.opacity))))
        mark.putalpha(alpha)

    margin = logo.margin
    if position == "bottom-right":
        pos = (canvas.width - target_w - margin, canvas.height - target_h - margin)
    elif position == "bottom-left":
        pos = (margin, canvas.height - target_h - margin)
    elif position == "top-right":
        pos = (canvas.width - target_w - margin, margin)
    else:  # top-left
        pos = (margin, margin)

    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(mark, dest=pos)
    return canvas.convert("RGB")


def _fit_to_canvas(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    target_ratio = target_w / target_h
    src_ratio = img.width / img.height

    if src_ratio > target_ratio:
        new_w = target_w
        new_h = int(target_w / src_ratio)
    else:
        new_h = target_h
        new_w = int(target_h * src_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(img, (offset_x, offset_y))
    return canvas


def validate_image(image_path: Path) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not image_path.exists():
        return ValidationResult(valid=False, errors=[f"File not found: {image_path}"])

    file_size = image_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        errors.append(f"File too large: {file_size / 1024 / 1024:.1f}MB (max 8MB)")

    try:
        with Image.open(image_path) as img:
            ratio = img.width / img.height
            if ratio < MIN_ASPECT_RATIO:
                errors.append(f"Aspect ratio {ratio:.2f} below minimum {MIN_ASPECT_RATIO}")
            elif ratio > MAX_ASPECT_RATIO:
                errors.append(f"Aspect ratio {ratio:.2f} exceeds maximum {MAX_ASPECT_RATIO}")
            if img.width < 320:
                warnings.append(f"Width {img.width}px is below recommended 320px")
    except Exception as exc:
        errors.append(f"Cannot read image: {exc}")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_carousel(image_paths: list[Path]) -> ValidationResult:
    """Valida um post do Instagram de 1 (imagem única) a 10 (carrossel) imagens."""
    all_errors: list[str] = []
    all_warnings: list[str] = []

    if len(image_paths) < MIN_CAROUSEL_IMAGES:
        all_errors.append(f"Post requires at least {MIN_CAROUSEL_IMAGES} image")
    if len(image_paths) > MAX_CAROUSEL_IMAGES:
        all_errors.append(
            f"Post exceeds {MAX_CAROUSEL_IMAGES} images ({len(image_paths)} given)"
        )

    for path in image_paths:
        result = validate_image(path)
        all_errors.extend(result.errors)
        all_warnings.extend(result.warnings)

    return ValidationResult(valid=len(all_errors) == 0, errors=all_errors, warnings=all_warnings)
