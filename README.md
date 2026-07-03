# Instagram Agent - impressam

Agent autonomo para gerar posts visuais para Instagram com IA, montar o carrossel, enviar uma previa para aprovacao humana no Telegram e publicar somente depois da confirmacao.

## Resumo do projeto

Este agent foi desenhado para operar um fluxo de publicacao semi-automatizado. Ele combina templates de prompt, agenda de execucao, geracao de imagens (Gemini por padrao, DALL-E opcional), composicao das pecas em formato compativel com Instagram, aprovacao manual via Telegram e publicacao via Buffer (com Cloudinary hospedando as imagens).

Objetivo pratico:
- reduzir o trabalho manual de criar conteudo visual recorrente;
- manter um humano no loop antes de qualquer acao na conta do Instagram;
- controlar custo de geracao por imagem e por periodo;
- registrar historico, erros e metricas de operacao.

## O que o agent faz

Fluxo principal:

```text
Gatilho (horario OU pedido no Telegram) -> Define assunto -> Gera imagens (Gemini) -> Compoe carrossel -> Envia preview no Telegram -> Aguarda aprovacao -> Cloudinary hospeda -> Buffer publica -> Salva historico e metricas
```

Comportamento operacional:
- carrega templates JSON ativos em `data/templates/`;
- carrega agendas em `data/schedules.json`;
- gera entre 1 e 10 imagens por post (imagem unica ou carrossel), respeitando o limite configurado no template e o teto tecnico do gerador;
- monta os arquivos finais em JPEG prontos para o Instagram;
- envia a previa para um chat autorizado no Telegram;
- aceita tres decisoes humanas: aprovar, rejeitar ou refazer;
- persiste posts, imagens geradas, custos e erros em SQLite.

## Tecnologias e dependencias

Stack principal:
- Python 3.11
- `google-genai` para geracao de imagem (`gemini-2.5-flash-image` por padrao)
- OpenAI SDK como provedor de imagem alternativo (`dall-e-3`, via `IMAGE_PROVIDER=openai`)
- `anthropic` (Claude) como "cerebro": pesquisa de mercado e redacao de legenda
- Buffer (API) para publicacao + Cloudinary para hospedagem das imagens
- `httpx` para chamadas HTTP e download de imagens
- `Pillow` para resize e processamento de imagem
- `python-telegram-bot` para comandos e aprovacao
- `APScheduler` para execucao agendada com cron
- `aiosqlite` para persistencia local
- `pydantic` e `pydantic-settings` para modelos e configuracao
- `pytest` para testes automatizados

## Arquitetura

Modulos principais:
- [src/main.py](src/main.py): orquestrador do agent e pipeline ponta a ponta.
- [src/config.py](src/config.py): leitura das variaveis de ambiente e defaults.
- [src/services/scheduler.py](src/services/scheduler.py): agenda jobs cron e escolhe templates.
- [src/services/gemini_image_generator.py](src/services/gemini_image_generator.py): provedor de imagem padrao (Gemini) — monta prompts, gera imagens e registra custo.
- [src/services/image_generator.py](src/services/image_generator.py): provedor de imagem alternativo (DALL-E, via `IMAGE_PROVIDER=openai`) — monta prompts, chama OpenAI, baixa imagens e registra custo.
- [src/services/post_composer.py](src/services/post_composer.py): processa imagens, gera caption e valida o carrossel.
- [src/services/telegram_bot.py](src/services/telegram_bot.py): envia preview, comandos e notificacoes.
- [src/handlers/approval_handler.py](src/handlers/approval_handler.py): resolve aprovacao, rejeicao e refacao.
- [src/services/buffer_publisher.py](src/services/buffer_publisher.py): publica o carrossel via API do Buffer, com cooldown entre posts.
- [src/services/image_host.py](src/services/image_host.py): hospeda as imagens (Cloudinary) e devolve URLs publicas para o Buffer.
- [src/services/storage.py](src/services/storage.py): persiste posts, imagens, erros e metricas.
- [src/utils/cost_tracker.py](src/utils/cost_tracker.py): controle de budget diario e mensal.
- [src/utils/image_processing.py](src/utils/image_processing.py): resize, watermark opcional e validacao tecnica das imagens.

## Regras de negocio

As regras mais importantes do agent hoje sao:

### 1. Publicacao sempre depende de aprovacao humana
- nenhum post e publicado automaticamente sem clique no Telegram;
- somente `TELEGRAM_CHAT_ID` autorizado pode interagir com o fluxo;
- se ninguem agir dentro de `TELEGRAM_APPROVAL_TIMEOUT`, o post expira e e descartado.

### 2. O agent trabalha orientado a templates
- cada template define prompt, variaveis, caption base, hashtags, quantidade de imagens e parametros do DALL-E;
- placeholders como `{style}` e `{mood}` sao preenchidos aleatoriamente com base nas opcoes do template;
- captions tambem podem reutilizar essas variaveis dinamicas.

### 3. O formato-alvo e post de Instagram (imagem unica ou carrossel)
- a validacao aceita de 1 (imagem unica) a 10 (carrossel) imagens por post;
- as imagens sao redimensionadas para `1080x1350`;
- o validador bloqueia arquivos acima de 8 MB e proporcoes fora da faixa suportada.

### 4. Existe controle de custo antes e durante a geracao
- o agent estima o custo com base em modelo e qualidade;
- se o lote exceder o budget diario ou mensal, a geracao falha antes de gastar;
- cada imagem gerada registra custo individual;
- um alerta interno dispara quando o uso atinge o threshold configurado.

### 5. Existe cooldown entre publicacoes
- por padrao, o agent nao publica dois posts com menos de 30 minutos de intervalo;
- o ultimo horario publicado e restaurado do banco ao reiniciar o processo.

### 6. Refazer tem limite
- no Telegram, o usuario pode pedir para refazer usando o mesmo template;
- o pipeline respeita `MAX_REDO_ATTEMPTS`;
- ao atingir o limite, o post e descartado e o operador e notificado.

### 7. Jobs agendados podem ter estrategia de selecao de template
- `random`: escolhe template aleatorio;
- `sequential` e `round_robin`: percorrem templates ativos em ordem;
- cada schedule tambem define `max_retries` para nova tentativa do job em caso de falha.

## Fluxo de execucao detalhado

1. O scheduler inicia e carrega templates ativos.
2. As agendas em `data/schedules.json` sao registradas com cron.
3. Quando um job dispara, o sistema escolhe um template.
4. O gerador (Gemini por padrao) cria e salva as imagens em `data/images/<post_id>/`.
5. O compositor redimensiona e valida as imagens finais.
6. O agent gera a caption e envia preview para o Telegram.
7. O operador aprova, rejeita ou pede refacao.
8. Se aprovado, o Cloudinary hospeda as imagens e o Buffer publica o carrossel.
9. O resultado e salvo em SQLite, junto com custos, timestamps e eventuais erros.

## Persistencia e dados

Arquivos e pastas relevantes:
- `data/templates/`: templates de geracao;
- `data/schedules.json`: jobs cron;
- `data/images/`: imagens brutas e compostas por post;
- `data/db/agent.db`: base SQLite com posts, imagens geradas e erros;
- `data/agent.log`: log operacional.

Tabelas principais do banco:
- `posts`
- `generated_images`
- `errors`

## Comandos do Telegram

Comandos implementados:
- `/start`: mostra o menu basico;
- `/status`: lista posts pendentes de aprovacao;
- `/history`: mostra os ultimos posts processados;
- `/schedule`: lista jobs agendados;
- `/pause`: pausa o scheduler;
- `/resume`: retoma o scheduler;
- `/force`: dispara geracao imediata usando um template disponivel;
- `/metrics`: mostra metricas de custo e aprovacao dos ultimos 30 dias.

## Hub de controle

Este agente foi desenhado para ser monitorado e administrado por um **Hub** (painel web,
projeto independente). O Hub leria o banco `data/db/agent.db` e a pasta `data/templates/` deste
agente em modo somente-leitura/edicao de templates, sem interferir no pipeline.

> **Status:** o Hub **ainda nao esta presente neste repositorio** (a pasta `hub/` nao existe aqui).
> O escopo planejado esta documentado em `scopes/frontend.md`. Integracao prevista com o backend
> via a porta `BriefingRepository` (ver `ARQUITETURA.md`).

## Configuracao

Variaveis de ambiente principais:
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `BUFFER_API_KEY`
- `BUFFER_CHANNEL_ID`
- `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DAILY_BUDGET_USD`
- `MONTHLY_BUDGET_USD`
- `BUDGET_ALERT_THRESHOLD`
- `TELEGRAM_APPROVAL_TIMEOUT`
- `POST_COOLDOWN_MINUTES`
- `MAX_REDO_ATTEMPTS`
- `SCHEDULER_TIMEZONE`
- `DB_PATH`

Defaults relevantes:
- provedor de imagem: `gemini` (`IMAGE_PROVIDER`); modelo: `gemini-2.5-flash-image`
- provedor alternativo: `openai` / `dall-e-3` (qualidade `hd`)
- timeout de aprovacao: `7200` segundos
- cooldown entre posts: `30` minutos
- maximo de tentativas de refacao: `3`
- timezone padrao do scheduler: `America/Sao_Paulo`

## Exemplo de template

```json
{
  "id": "sunset_landscape",
  "name": "Paisagens ao Por do Sol",
  "prompt": "A breathtaking {style} landscape at sunset, {color_palette} color palette, {mood} atmosphere",
  "variables": {
    "style": ["realistic", "watercolor"],
    "color_palette": ["warm golden", "deep crimson"],
    "mood": ["serene", "dramatic"]
  },
  "caption_template": "Momentos que inspiram.",
  "hashtag_pool": ["#aiart", "#landscape"],
  "image_count": 4,
  "dalle_params": {
    "size": "1024x1792",
    "quality": "hd",
    "style": "vivid"
  },
  "active": true
}
```

## Como rodar

Instalacao:

```bash
pip install -r requirements.txt
```

Configuracao:

```bash
copy .env.example .env
```

Execucao:

```bash
python -m src.main
```

Testes:

```bash
pytest tests -v
```

## Observacoes e limites atuais

- o agent hoje e focado em imagem e carrossel, nao em video ou Reels;
- o controle de budget fica em memoria durante a execucao atual do processo, embora o custo total por post fique salvo no banco;
- a publicacao depende de a imagem estar hospedada numa URL publica (Cloudinary), pois o Buffer baixa a imagem da URL na hora de criar o post;
- existe tratamento de retry no scheduler e cooldown entre publicacoes no publisher.
