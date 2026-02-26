# Instagram Agent 🤖📸

Agente que processa uma mensagem, gera conteúdo (imagem + legenda com hashtags) usando IA, apresenta para aprovação humana e publica no Instagram via Graph API.

## Fluxo

```
Mensagem → Gera legenda (IA) + Imagem (IA) → Preview/Aprovação → Publica no Instagram
```

## Pré-requisitos

- Python 3.11+
- Conta Instagram **Business** ou **Creator** conectada a uma Página do Facebook
- Token de acesso da Instagram Graph API com permissão `instagram_content_publish`
- API Key do Google Gemini (ou OpenAI)

## Setup

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env com seus tokens
```

## Uso

O agente opera em 4 passos:

### 1. Gerar legenda com IA
```bash
python execution/generate_caption.py --message "Lançamento do nosso novo produto!"
# Output: .tmp/caption.json
```

Prompt adicional (opcional):
```bash
# Arquivo padrao lido automaticamente:
directives/caption_additional_prompt.md

# Se quiser outro arquivo:
python execution/generate_caption.py --message "..." --prompt-file "directives/meu_prompt.md"
```

### 2. Gerar imagem com IA (ou usar a sua)
```bash
# Gerar via IA
python execution/generate_image.py --prompt "Produto de skincare em fundo branco minimalista"

# Ou usar imagem própria
python execution/generate_image.py --user-file "caminho/para/imagem.jpg"
# Output: .tmp/media/image.png
```

### 3. Revisar e aprovar
```bash
python execution/preview_post.py
# Exibe preview interativo no terminal
# Opções: yes / no / edit caption / new image
```

### 4. Publicar no Instagram
```bash
# Imagem
python execution/post_to_instagram.py --media-type image

# Reels (vídeo)
python execution/post_to_instagram.py --media-type reel
# Output: .tmp/post_result.json
```

### Extra: Consultar custo e tokens da OpenAI
```bash
# Janela padrão: últimos 30 dias (UTC)
python execution/check_openai_usage.py

# Janela customizada
python execution/check_openai_usage.py --days 7
python execution/check_openai_usage.py --start-date 2026-02-01 --end-date 2026-02-22
# Output: .tmp/openai_usage.json
```

## Estrutura

```
agent-instagram/
├── directives/           # SOPs (Layer 1 - O quê fazer)
│   ├── generate_content.md
│   ├── generate_media.md
│   ├── approval_flow.md
│   └── post_instagram.md
├── execution/            # Scripts Python (Layer 3 - Execução)
│   ├── generate_caption.py
│   ├── generate_image.py
│   ├── preview_post.py
│   └── post_to_instagram.py
├── .tmp/                 # Arquivos intermediários (não comitar)
│   └── media/
├── .env.example          # Template de variáveis de ambiente
├── requirements.txt
└── README.md
```

> **Layer 2 (Orchestration)** é você — leia as diretivas, chame os scripts na ordem certa, trate erros e melhore o sistema.

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | ✅ | Token de acesso Graph API |
| `INSTAGRAM_ACCOUNT_ID` | ✅ | ID da conta Business/Creator |
| `GEMINI_API_KEY` | ✅ | Google Gemini API Key |
| `OPENAI_API_KEY` | ❌ | OpenAI (fallback opcional) |
| `OPENAI_ADMIN_API_KEY` | ❌ | Chave Admin para consultar custos/uso da organização na OpenAI |
| `OPENAI_ORG_ID` | ❌ | ID da organização OpenAI (opcional, multi-org) |
| `MEDIA_PROVIDER` | ❌ | `gemini` (padrão) ou `openai` |
| `POST_LANGUAGE` | ❌ | `pt-BR` (padrão) |
| `POST_TONE` | ❌ | `engaging` (padrão) |
| `CAPTION_PROMPT_FILE` | ❌ | Arquivo `.md` com instruções extras de legenda |
## Arquitetura DOE

Este projeto segue a arquitetura **Directive-Orchestration-Execution**:

- **Directives** (`directives/`): SOPs em Markdown — definem *o quê* fazer
- **Orchestration**: O agente de IA — lê as diretivas, toma decisões, trata erros
- **Execution** (`execution/`): Scripts Python determinísticos — fazem *o trabalho*
