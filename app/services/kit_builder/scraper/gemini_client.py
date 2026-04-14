"""
Gemini API client for Kit Builder.
Gera título e descrição unificados para um kit composto por múltiplos produtos.
"""
import logging
import json
import re
import time
from google import genai
from typing import Dict, List
from app.core.config import settings

logger = logging.getLogger(__name__)


class KitBuilderGeminiClient:
    """
    Gera descrição e título profissional para kits compostos por múltiplos produtos.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_text = getattr(settings, "GEMINI_MODEL_TEXT", "gemini-1.5-flash")

    def generate_kit_content(self, products: List[Dict], central_idx: int = 0) -> Dict:
        """
        Recebe lista de produtos individuais e gera:
        - Título do kit
        - Descrição unificada e profissional em steps

        Retorna dict com: titulo_kit, descricao, usage (input/output tokens).
        """
        logger.info(f"🤖 [Kit Copywriter] Gerando conteúdo para kit com {len(products)} produtos (central: idx {central_idx})...")
        prompt = self._build_kit_prompt(products, central_idx)

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_text,
                    contents=prompt
                )

                usage = response.usage_metadata
                u_data = {
                    "input": int(usage.prompt_token_count or 0),
                    "output": int(usage.candidates_token_count or 0)
                }

                json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
                data = json.loads(json_match.group(0)) if json_match else {}

                return {
                    "titulo_kit": data.get("titulo_kit", "").strip(),
                    "descricao":  data.get("descricao", "").strip(),
                    "usage": u_data
                }

            except Exception as e:
                if ("503" in str(e) or "429" in str(e)) and attempt < max_retries - 1:
                    logger.warning(f"⚠️ Google ocupado (Tentativa {attempt + 1}). Retentando...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logger.error(f"❌ Falha na geração do kit: {e}")
                return {"titulo_kit": "", "descricao": "", "usage": {"input": 0, "output": 0}}

        return {"titulo_kit": "", "descricao": "", "usage": {"input": 0, "output": 0}}

    def _build_kit_prompt(self, products: List[Dict], central_idx: int = 0) -> str:
        """
        Monta o prompt estruturado em steps para minimizar alucinações.
        O produto central é o eixo do kit; os demais são acessórios/complementos.
        """
        central = products[central_idx] if central_idx < len(products) else products[0]
        accessories = [p for i, p in enumerate(products) if i != central_idx]

        def _fmt_product(p: Dict, role: str) -> str:
            comprimento = p.get("comprimento") or p.get("profundidade") or ""
            dims_parts = [p.get("largura",""), comprimento, p.get("altura","")]
            dims = " x ".join(d for d in dims_parts if d)
            qty = p.get("quantidade", 1)
            qty_str = f"{qty}x " if qty > 1 else ""
            return (
                f"  [{role}] {qty_str}{p.get('titulo', 'Produto sem título')}\n"
                f"    - Quantidade: {qty} unidade(s)\n"
                f"    - Dimensões individuais (L x C x A): {dims or 'não informado'}\n"
                f"    - Peso individual: {p.get('peso', 'não informado')}\n"
            )

        central_block = _fmt_product(central, "PRODUTO CENTRAL")
        acc_block = "\n".join(
            _fmt_product(a, f"COMPLEMENTO {i+1}") for i, a in enumerate(accessories)
        ) or "  (nenhum complemento)"

        return f"""Você é um especialista em criação de fichas de produto para e-commerce de alto padrão da marca Brazil Home Living.

Você receberá a composição de um KIT e deverá gerar um título e uma descrição profissional.
Siga os PASSOS abaixo na ordem. Não pule nenhum passo. Não invente dados que não foram fornecidos.

════════════════════════════════════════
COMPOSIÇÃO DO KIT
════════════════════════════════════════

{central_block}
{acc_block}

════════════════════════════════════════
PASSO 1 — TÍTULO DO KIT
════════════════════════════════════════
Regras do título:
- Formato: "Kit [nome do produto central] + [resumo dos complementos com quantidade]"
- Exemplos corretos: "Kit Mesa de Jantar Extensível + 6 Cadeiras", "Kit Bancada de Jardim + 2 Bancos"
- Máximo 90 caracteres.
- Não cite marcas de lojas. Não use emojis.

════════════════════════════════════════
PASSO 2 — DESCRIÇÃO DO KIT
════════════════════════════════════════
Escreva EXATAMENTE 5 parágrafos, nesta ordem:

PARÁGRAFO 1 — Apresentação do conjunto:
Descreva o kit como uma solução completa. Apresente o produto central e como os complementos o enriquecem.
Não invente características. Use apenas o que foi informado acima.

PARÁGRAFO 2 — Design e Estética:
Descreva a harmonia visual entre os itens: materiais, cores (se informados), linhas do design.
Se não foram informados, foque na coerência estética do conjunto sem inventar detalhes.

PARÁGRAFO 3 — Qualidade e Diferenciais Técnicos:
Cite os aspectos técnicos fornecidos (dimensões, materiais, peso).
Não invente especificações que não estão na composição acima.

PARÁGRAFO 4 — Uso e Ambientes:
Sugira ambientes e situações de uso ideais para o conjunto.

PARÁGRAFO 5 — Itens Inclusos (OBRIGATÓRIO — não omitir):
Liste com precisão o que está incluso no kit.
Formato: "Este kit inclui: [quantidade] [produto central] e [quantidade] [complemento]..."
Informe as dimensões individuais de cada item apenas se foram fornecidas acima.

RESUMO FINAL (após os 5 parágrafos):
Liste as principais especificações em linhas separadas, sem marcadores. Exemplo:
Dimensões do produto central: ...
Quantidade de itens no kit: ...
Material: ...

════════════════════════════════════════
REGRAS ABSOLUTAS
════════════════════════════════════════
- Nunca cite Leroy Merlin, Sodimac, Decathlon, Sam's Club ou qualquer loja.
- Nunca invente dimensões, pesos ou materiais não fornecidos.
- A ÚNICA marca que pode aparecer no título e na descrição é "Brazil Home Living". Nunca mencione qualquer outra marca, mesmo que ela apareça nos títulos dos produtos fornecidos.
- Nunca mencione modelos, códigos de referência, SKUs ou numerações de modelo (ex: "Modelo XYZ-123", "Ref. 456789"). Se o título contiver um código, ignore-o completamente.
- Sem emojis, sem HTML, sem preços, sem asteriscos, sem hifens como marcadores.
- Linguagem formal, clara e inspiradora.

════════════════════════════════════════
FORMATO DE RESPOSTA
════════════════════════════════════════
Retorne APENAS o JSON abaixo, sem nenhum texto antes ou depois:
{{
  "titulo_kit": "...",
  "descricao": "..."
}}
"""


# Singleton
_gemini_client = None


def get_gemini_client() -> KitBuilderGeminiClient:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = KitBuilderGeminiClient()
    return _gemini_client
