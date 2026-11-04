import random
from pathlib import Path

from ..config import Settings
from ..domain.models.template import PromptTemplate
from ..utils.cost_tracker import BudgetTracker
from ..utils.logger import get_logger

logger = get_logger(__name__)

MAX_IMAGES = 10


class BaseImageGenerator:
    _BRAND_BRIEF_LABEL = "Diretrizes de marca a respeitar:"
    _SUBJECT_LABEL = "Assunto do post:"

    def __init__(self, settings: Settings, budget_tracker: BudgetTracker):
        self._settings = settings
        self._budget = budget_tracker
        self._images_dir = settings.images_dir

    def _build_prompt(self, template: PromptTemplate, image_brief: str = "", subject: str = "") -> str:
        prompt = template.prompt
        for var_name, choices in template.variables.items():
            if choices:
                prompt = prompt.replace(f"{{{var_name}}}", random.choice(choices))

        parts: list[str] = []
        if image_brief.strip():
            parts.append(f"{self._BRAND_BRIEF_LABEL}\n{image_brief.strip()}")
        if subject.strip():
            parts.append(f"{self._SUBJECT_LABEL} {subject.strip()}")
        parts.append(prompt)
        return "\n\n".join(parts)

    def _ensure_budget(self, total_cost: float) -> None:
        if not self._budget.can_spend(total_cost):
            s = self._budget.summary()
            raise RuntimeError(
                f"Budget exceeded — cannot spend ${total_cost:.3f}. "
                f"Daily: ${s['daily_spent']}/{s['daily_limit']}, "
                f"Monthly: ${s['monthly_spent']}/{s['monthly_limit']}"
            )

    def _warn_if_near_budget(self) -> None:
        if self._budget.near_alert():
            logger.warning("Budget alert: approaching limit. Summary: %s", self._budget.summary())

    def _save(self, data: bytes, post_id: str, index: int, ext: str) -> Path:
        save_dir = self._images_dir / post_id
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / f"raw_{index}.{ext}"
        file_path.write_bytes(data)
        logger.debug("Imagem %d salva em %s (%d bytes)", index, file_path, len(data))
        return file_path
