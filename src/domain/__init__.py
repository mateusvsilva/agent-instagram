"""Camada de domínio: modelos e contratos (portas).

Esta camada não depende de infraestrutura (`services/`) nem de SDKs externos
(openai, google-genai, anthropic, telegram). Define os contratos que os
adaptadores concretos implementam, seguindo a regra de dependência: as setas
apontam para dentro (infraestrutura depende do domínio, nunca o contrário).
"""
