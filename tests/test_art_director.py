from unittest.mock import AsyncMock, MagicMock
from src.services.art_director import ArtDirectorService


def _brand():
    b = MagicMock()
    b.image_brief.return_value = "DIRETRIZES: editorial, aço, azul #1B4D7E"
    return b


async def test_build_prompt_includes_brand_and_returns_text():
    brain = MagicMock()
    brain.complete = AsyncMock(return_value="  macro shot of a gear  ")
    art = ArtDirectorService(brain=brain, brand=_brand())
    out = await art.build_image_prompt("uma engrenagem", mode="clean")
    assert out == "macro shot of a gear"
    sys_arg, user_arg = brain.complete.call_args.args[0], brain.complete.call_args.args[1]
    assert "DIRETRIZES" in user_arg and "engrenagem" in user_arg


async def test_banner_mode_instructs_uppercase_no_accent():
    brain = MagicMock()
    brain.complete = AsyncMock(return_value="banner")
    art = ArtDirectorService(brain=brain, brand=_brand())
    await art.build_image_prompt("quando vale 3D", mode="banner")
    system = brain.complete.call_args.args[0]
    assert "CAIXA ALTA" in system and "ACENTO" in system.upper()


async def test_revise_passes_current_and_feedback():
    brain = MagicMock()
    brain.complete = AsyncMock(return_value="darker gear")
    art = ArtDirectorService(brain=brain, brand=_brand())
    out = await art.revise_image_prompt("a gear", "mais escuro")
    assert out == "darker gear"
    user = brain.complete.call_args.args[1]
    assert "a gear" in user and "mais escuro" in user
