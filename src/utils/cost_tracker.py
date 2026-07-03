from datetime import datetime, timezone

from ..utils.logger import get_logger

logger = get_logger(__name__)

COST_TABLE: dict[tuple[str, str], float] = {
    ("dall-e-3", "standard"): 0.040,
    ("dall-e-3", "hd"): 0.080,
    ("dall-e-2", "standard"): 0.020,
    # gpt-image-1 (custo aprox. por imagem 1024x1536; OpenAI cobra por tokens)
    ("gpt-image-1", "low"): 0.020,
    ("gpt-image-1", "medium"): 0.070,
    ("gpt-image-1", "high"): 0.190,
}


def cost_per_image(model: str = "dall-e-3", quality: str = "hd") -> float:
    return COST_TABLE.get((model, quality), 0.040)


class BudgetTracker:
    def __init__(self, daily_limit: float, monthly_limit: float, alert_threshold: float = 0.8):
        self._daily_limit = daily_limit
        self._monthly_limit = monthly_limit
        self._alert_threshold = alert_threshold
        self._daily_spent: dict[str, float] = {}
        self._monthly_spent: dict[str, float] = {}

    def _day_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _month_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def record(self, amount: float) -> None:
        day = self._day_key()
        month = self._month_key()
        self._daily_spent[day] = self._daily_spent.get(day, 0.0) + amount
        self._monthly_spent[month] = self._monthly_spent.get(month, 0.0) + amount
        logger.debug("Budget recorded: $%.4f | daily total: $%.4f | monthly total: $%.4f",
                     amount, self.daily_spent, self.monthly_spent)

    @property
    def daily_spent(self) -> float:
        return self._daily_spent.get(self._day_key(), 0.0)

    @property
    def monthly_spent(self) -> float:
        return self._monthly_spent.get(self._month_key(), 0.0)

    def can_spend(self, amount: float) -> bool:
        return (
            self.daily_spent + amount <= self._daily_limit
            and self.monthly_spent + amount <= self._monthly_limit
        )

    def near_alert(self) -> bool:
        daily_ratio = self.daily_spent / self._daily_limit if self._daily_limit else 0
        monthly_ratio = self.monthly_spent / self._monthly_limit if self._monthly_limit else 0
        return max(daily_ratio, monthly_ratio) >= self._alert_threshold

    def summary(self) -> dict:
        return {
            "daily_spent": round(self.daily_spent, 4),
            "daily_limit": self._daily_limit,
            "monthly_spent": round(self.monthly_spent, 4),
            "monthly_limit": self._monthly_limit,
        }
