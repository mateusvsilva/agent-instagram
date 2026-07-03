"""Diretor de arte: traduz o brief/feedback do operador em prompt de imagem.

Usa a porta BrainClient (cérebro de texto) + as diretrizes de marca (image_brief).
Não chama o modelo de imagem — só produz o texto do prompt.
"""
from ..domain.models.brand import BrandIdentity
from ..domain.ports import BrainClient

_SYSTEM_BUILD = (
    "Você é diretor de arte de uma marca de impressão 3D industrial. Com base nas "
    "diretrizes de marca e no pedido do operador, escreva UM prompt de geração de "
    "imagem em INGLÊS (descrição de cena, estilo e iluminação), conciso, seguindo as "
    "diretrizes. Se o formato for banner, o TEXTO QUE APARECE DENTRO DA IMAGEM deve "
    "ser em PORTUGUÊS DO BRASIL, curto, em CAIXA ALTA e SEM ACENTO, citado entre aspas "
    "exatamente como deve aparecer na arte — ex.: ...short bold overlay text "
    '"FORA DE LINHA? A GENTE IMPRIME".... NUNCA escreva o texto do banner em inglês. '
    "Responda APENAS com o prompt (sem aspas envolvendo a resposta inteira) e sem explicação."
)
_SYSTEM_REVISE = (
    "Você é diretor de arte de uma marca de impressão 3D industrial. Receberá um "
    "prompt de imagem atual (em inglês) e um ajuste pedido pelo operador (em "
    "português). Devolva o prompt REVISADO em INGLÊS, incorporando o ajuste e "
    "mantendo o estilo da marca. Qualquer TEXTO QUE APAREÇA DENTRO DA IMAGEM deve "
    "permanecer em PORTUGUÊS DO BRASIL, em CAIXA ALTA e SEM ACENTO. "
    "Responda APENAS com o prompt."
)
_MODE_LABELS = {
    "clean": "foto limpa do produto, sem texto na imagem",
    "banner": "banner com um texto curto em português (CAIXA ALTA, sem acento) sobre a imagem",
    "auto": "decida o melhor formato (foto limpa ou banner)",
}


class ArtDirectorService:
    def __init__(self, brain: BrainClient, brand: BrandIdentity, max_tokens: int = 400):
        self._brain = brain
        self._brand = brand
        self._max_tokens = max_tokens

    async def build_image_prompt(self, brief: str, mode: str = "auto") -> str:
        user = self._compose_build_user(brief, mode)
        out = await self._brain.complete(_SYSTEM_BUILD, user, max_tokens=self._max_tokens)
        return out.strip()

    async def revise_image_prompt(self, current_prompt: str, feedback: str) -> str:
        user = f"PROMPT ATUAL:\n{current_prompt}\n\nAJUSTE PEDIDO:\n{feedback}"
        out = await self._brain.complete(_SYSTEM_REVISE, user, max_tokens=self._max_tokens)
        return out.strip()

    def _compose_build_user(self, brief: str, mode: str) -> str:
        parts: list[str] = []
        brief_marca = self._brand.image_brief()
        if brief_marca.strip():
            parts.append("=== DIRETRIZES DE MARCA ===\n" + brief_marca.strip())
        parts.append("=== FORMATO ===\n" + _MODE_LABELS.get(mode, _MODE_LABELS["auto"]))
        parts.append("=== PEDIDO DO OPERADOR ===\n" + brief.strip())
        return "\n\n".join(parts)
