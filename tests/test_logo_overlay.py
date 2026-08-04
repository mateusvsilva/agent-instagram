from pathlib import Path

from PIL import Image

from src.utils.image_processing import (
    INSTAGRAM_CAROUSEL_HEIGHT,
    INSTAGRAM_CAROUSEL_WIDTH,
    LogoOverlay,
    apply_logo,
    resize_for_instagram,
)


def _make_logo(path: Path, size=(400, 200)) -> None:
    logo = Image.new("RGBA", size, (255, 0, 0, 255))
    logo.save(path)


def test_apply_logo_preserves_canvas_size_and_mode(tmp_path):
    canvas = Image.new("RGB", (1080, 1350), (10, 20, 30))
    logo_path = tmp_path / "logo.png"
    _make_logo(logo_path)

    result = apply_logo(canvas, LogoOverlay(path=logo_path, scale=0.2, opacity=0.9))

    assert result.size == (1080, 1350)
    assert result.mode == "RGB"


def test_apply_logo_scales_to_fraction_of_width(tmp_path):
    canvas = Image.new("RGB", (1000, 1000), (0, 0, 0))
    logo_path = tmp_path / "logo.png"
    _make_logo(logo_path, size=(500, 250))

    # scale=0.2 → logo com 200px de largura → altera pixels no canto inferior direito.
    result = apply_logo(canvas, LogoOverlay(path=logo_path, scale=0.2, margin=10, opacity=1.0))

    # Pixel dentro da área esperada do logo deve estar avermelhado (não mais preto).
    px = result.getpixel((1000 - 100, 1000 - 100))
    assert px[0] > 100


def test_apply_logo_missing_file_is_noop(tmp_path):
    canvas = Image.new("RGB", (500, 500), (7, 7, 7))
    result = apply_logo(canvas, LogoOverlay(path=tmp_path / "inexistente.png"))
    assert result.getpixel((250, 250)) == (7, 7, 7)


def test_resize_for_instagram_with_logo(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (1024, 1280), (50, 50, 50)).save(src)
    logo_path = tmp_path / "logo.png"
    _make_logo(logo_path)
    out = tmp_path / "out.jpg"

    result_path = resize_for_instagram(src, out, logo=LogoOverlay(path=logo_path))

    with Image.open(result_path) as img:
        assert img.size == (INSTAGRAM_CAROUSEL_WIDTH, INSTAGRAM_CAROUSEL_HEIGHT)


def test_resize_for_instagram_without_logo_still_works(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (1024, 1280), (50, 50, 50)).save(src)
    out = tmp_path / "out.jpg"

    result_path = resize_for_instagram(src, out)

    with Image.open(result_path) as img:
        assert img.size == (INSTAGRAM_CAROUSEL_WIDTH, INSTAGRAM_CAROUSEL_HEIGHT)
