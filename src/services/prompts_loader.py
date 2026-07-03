"""Lê a pasta `prompts/` e a transforma em uma `BrandIdentity` (HU-BACKEND-05).

Até agora os arquivos de marca eram só scaffold; este serviço é a ponte que
faltava entre `prompts/` e o pipeline. Ele também detecta seções incompletas
(arquivo ausente, vazio ou ainda com marcadores `> PREENCHER:`) e registra um
aviso previsível em log — o comportamento de fallback exigido pelo critério de
aceite quando a identidade de marca está incompleta.
"""
from pathlib import Path

from ..config import Settings
from ..domain.models.brand import BrandIdentity
from ..utils.logger import get_logger

logger = get_logger(__name__)

_PLACEHOLDER_MARKER = "> PREENCHER:"

# Nome lógico → arquivo na pasta prompts/.
_PROMPT_FILES = {
    "identity": "identity.md",
    "image_guidelines": "image_guidelines.md",
    "caption_guidelines": "caption_guidelines.md",
    "hashtag_strategy": "hashtag_strategy.md",
}


class PromptsLoaderService:
    def __init__(self, settings: Settings):
        self._prompts_dir = settings.prompts_dir

    def load(self) -> BrandIdentity:
        sections: dict[str, str] = {}
        incomplete: list[str] = []

        for logical_name, filename in _PROMPT_FILES.items():
            content = self._read_file(self._prompts_dir / filename)
            sections[logical_name] = content
            if self._is_incomplete(content):
                incomplete.append(logical_name)

        if incomplete:
            logger.warning(
                "Identidade de marca incompleta — seções ausentes/vazias/'> PREENCHER:': %s. "
                "O pipeline segue, mas a qualidade alinhada à marca fica reduzida até preencher "
                "os arquivos em %s.",
                ", ".join(incomplete),
                self._prompts_dir,
            )
        else:
            logger.info("Identidade de marca carregada de %s (todas as seções preenchidas).", self._prompts_dir)

        return BrandIdentity(
            identity=sections["identity"],
            image_guidelines=sections["image_guidelines"],
            caption_guidelines=sections["caption_guidelines"],
            hashtag_strategy=sections["hashtag_strategy"],
            incomplete_sections=incomplete,
        )

    def _read_file(self, path: Path) -> str:
        if not path.exists():
            logger.warning("Arquivo de marca não encontrado: %s", path)
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.error("Falha ao ler arquivo de marca %s: %s", path, exc)
            return ""

    @staticmethod
    def _is_incomplete(content: str) -> bool:
        if not content.strip():
            return True
        return _PLACEHOLDER_MARKER in content
