from pathlib import Path

from ..config import Settings
from ..domain.models.brand import BrandIdentity
from ..utils.logger import get_logger

logger = get_logger(__name__)

_PLACEHOLDER_MARKER = "> PREENCHER:"
_SECTIONS = ("identity", "image_guidelines", "caption_guidelines", "hashtag_strategy")


class PromptsLoaderService:
    def __init__(self, settings: Settings):
        self._prompts_dir = settings.prompts_dir

    def load(self) -> BrandIdentity:
        sections = {name: self._read(self._prompts_dir / f"{name}.md") for name in _SECTIONS}
        incomplete = [name for name, text in sections.items() if not text or _PLACEHOLDER_MARKER in text]
        if incomplete:
            logger.warning(
                "Identidade de marca incompleta — seções ausentes/vazias/'%s': %s. Preencha os arquivos em %s.",
                _PLACEHOLDER_MARKER, ", ".join(incomplete), self._prompts_dir,
            )
        else:
            logger.info("Identidade de marca carregada de %s.", self._prompts_dir)
        return BrandIdentity(**sections)

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            logger.warning("Arquivo de marca não encontrado: %s", path)
        except OSError as exc:
            logger.error("Falha ao ler arquivo de marca %s: %s", path, exc)
        return ""
