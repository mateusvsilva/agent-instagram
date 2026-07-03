"""Base comum dos geradores de imagem (DALL-E e Gemini).

Concentra o que as duas implementações faziam idêntico — montagem do prompt
(brief de marca + assunto + prompt do template), checagem de orçamento e alerta
de budget — para que cada provider concreto cuide só do que é específico do seu
SDK (chamada à API, salvamento do arquivo, custo por imagem).

As implementações concretas (`ImageGeneratorService`, `GeminiImageGeneratorService`)
satisfazem a porta `ImageGenerator` e sobrescrevem os labels do prompt para
preservar o texto exato que cada modelo já recebia.
"""
import random

from ..config import Settings
from ..domain.models.template import PromptTemplate
from ..utils.cost_tracker import BudgetTracker
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BaseImageGenerator:
    # Labels do prompt — cada provider mantém o texto que já usava para não
    # alterar o resultado das gerações existentes.
    _BRAND_BRIEF_LABEL = "Diretrizes de marca a respeitar:"
    _SUBJECT_LABEL = "Assunto do post:"

    def __init__(self, settings: Settings, budget_tracker: BudgetTracker):
        self._settings = settings
        self._budget = budget_tracker
        self._images_dir = settings.images_dir

    def _build_prompt(self, template: PromptTemplate, image_brief: str = "", subject: str = "") -> str:
        """Monta o prompt final: [diretrizes de marca] + [assunto] + [prompt do template]."""
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
        """Levanta RuntimeError se o gasto estouraria o orçamento diário/mensal."""
        if not self._budget.can_spend(total_cost):
            summary = self._budget.summary()
            raise RuntimeError(
                f"Budget exceeded — cannot spend ${total_cost:.3f}. "
                f"Daily: ${summary['daily_spent']}/{summary['daily_limit']}, "
                f"Monthly: ${summary['monthly_spent']}/{summary['monthly_limit']}"
            )

    def _warn_if_near_budget(self) -> None:
        if self._budget.near_alert():
            logger.warning("Budget alert: approaching limit. Summary: %s", self._budget.summary())
