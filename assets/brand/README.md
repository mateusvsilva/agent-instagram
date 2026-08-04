# Assets de marca

Coloque aqui os arquivos visuais **estáveis** da marca (versionados no git),
diferente de `data/`, que é conteúdo gerado em runtime.

## Logo

O agente sobrepõe o logo real por cima de cada imagem gerada — assim ele sai
**exato** (pixel-perfect), sem gastar API e sem o risco de a IA deformar as letras.

**Como ativar:**

1. Salve o logo como **`logo.png`** nesta pasta.
   - PNG com **fundo transparente** (canal alpha).
   - Resolução alta (ex.: ≥ 600px de largura) — ele é reduzido, então quanto maior, mais nítido.
   - Versão que contraste com fundos claros/escuros (o overlay não troca de cor sozinho).
2. No `.env`, ligue e ajuste:

   ```
   LOGO_ENABLED=true
   LOGO_PATH=./assets/brand/logo.png
   LOGO_POSITION=bottom-right   # bottom-right | bottom-left | top-right | top-left
   LOGO_SCALE=0.18              # largura do logo = 18% da largura da imagem
   LOGO_MARGIN=48              # px de distância da borda
   LOGO_OPACITY=0.9            # 0.0 (transparente) a 1.0 (opaco)
   ```
3. Reinicie o serviço: `systemctl restart instagram-agent`.

Se `LOGO_ENABLED=false` (padrão) ou o arquivo não existir, o agente publica a
imagem sem logo — não quebra nada.
