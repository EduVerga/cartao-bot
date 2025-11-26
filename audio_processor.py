"""
Módulo para processar áudios de voz e extrair informações de gastos
"""
import google.generativeai as genai
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Processa áudios de voz para extrair informações de gastos"""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

        # Auto-detecta modelos disponíveis
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)

        # Prioriza APENAS modelos flash (têm tier gratuito generoso)
        # Evita modelos pro/exp que têm quotas mais restritivas
        flash_models = [m for m in available_models if 'flash' in m.lower() and 'pro' not in m.lower()]

        if flash_models:
            models_to_try = flash_models
        else:
            # Fallback: qualquer modelo disponível
            models_to_try = available_models

        if not models_to_try:
            models_to_try = available_models

        if models_to_try:
            model_name = models_to_try[0].replace('models/', '')
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"[AudioProcessor] Usando modelo: {model_name}")
        else:
            raise Exception("Nenhum modelo Gemini disponível para áudio.")

    def processar_audio(self, audio_path: str) -> dict:
        """
        Processa áudio e extrai informações de gasto

        Returns:
            dict com: valor, estabelecimento, categoria_sugerida, descricao
        """
        try:
            # Upload do arquivo de áudio
            audio_file = genai.upload_file(path=audio_path)

            prompt = """
Você é um assistente financeiro. Ouça este áudio e extraia as informações sobre o gasto mencionado.

Retorne as informações em formato JSON:

{
  "valor": <valor numérico do gasto, apenas número>,
  "estabelecimento": "<nome do lugar onde foi o gasto, se mencionado>",
  "categoria_sugerida": "<categoria: Alimentação fora de casa, Supermercado, Transporte, Saúde, Lazer, Compras, Contas, Outros>",
  "descricao": "<breve descrição do que foi dito no áudio>",
  "metodo_pagamento": "<forma de pagamento mencionada: pix, dinheiro, débito, crédito, ou null se não mencionado>"
}

Regras:
- Se não conseguir identificar o valor, retorne null
- Para estabelecimento, use o nome exato mencionado ou "Não especificado"
- Para categoria, analise o contexto do gasto e sugira a mais apropriada
- A descrição deve ser um resumo curto do que a pessoa disse
- Se não mencionar forma de pagamento, use null

Exemplos de frases que podem ser ditas:
- "Gastei 100 reais no supermercado"
- "Paguei 50 reais de Uber hoje"
- "Almocei no restaurante, foram 45 reais"
- "Comprei remédio na farmácia, 80 reais no pix"

Retorne APENAS o JSON, sem texto adicional.
"""

            response = self.model.generate_content([prompt, audio_file])

            # Limpa a resposta
            response_text = response.text.strip()
            logger.info(f"Resposta bruta do Gemini: {response_text}")

            # Remove possíveis markdown code blocks
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                if lines[0].startswith('```json'):
                    response_text = '\n'.join(lines[1:-1])
                else:
                    response_text = '\n'.join(lines[1:-1])

            logger.info(f"JSON limpo: {response_text}")
            dados = json.loads(response_text)

            # Valida e formata os dados
            return self._validar_dados(dados)

        except Exception as e:
            import traceback
            logger.error(f"Erro ao processar áudio: {e}")
            logger.error(f"Traceback completo:\n{traceback.format_exc()}")
            return None

    def _validar_dados(self, dados: dict) -> dict:
        """Valida e formata os dados extraídos do áudio"""
        resultado = {
            'valor': None,
            'estabelecimento': 'Não especificado',
            'categoria_sugerida': 'Outros',
            'descricao': '',
            'metodo_pagamento': None
        }

        # Valida valor
        if 'valor' in dados and dados['valor']:
            try:
                resultado['valor'] = float(dados['valor'])
            except (ValueError, TypeError):
                pass

        # Valida estabelecimento
        if 'estabelecimento' in dados and dados['estabelecimento']:
            resultado['estabelecimento'] = str(dados['estabelecimento']).upper()

        # Valida categoria
        categorias_validas = [
            'Alimentação fora de casa',
            'Supermercado',
            'Transporte',
            'Saúde',
            'Lazer',
            'Compras',
            'Contas',
            'Outros'
        ]

        if 'categoria_sugerida' in dados and dados['categoria_sugerida'] in categorias_validas:
            resultado['categoria_sugerida'] = dados['categoria_sugerida']

        # Descrição
        if 'descricao' in dados and dados['descricao']:
            resultado['descricao'] = str(dados['descricao'])

        # Método de pagamento
        if 'metodo_pagamento' in dados and dados['metodo_pagamento']:
            resultado['metodo_pagamento'] = str(dados['metodo_pagamento']).lower()

        return resultado

    def processar_texto(self, texto: str) -> dict:
        """
        Processa texto livre e extrai informações de gasto

        Args:
            texto: Texto livre como "Gastei 100 reais no supermercado"

        Returns:
            dict com: valor, estabelecimento, categoria_sugerida, descricao
        """
        try:
            prompt = f"""
Você é um assistente financeiro. Analise este texto e extraia as informações sobre o gasto mencionado:

"{texto}"

Retorne as informações em formato JSON:

{{
  "valor": <valor numérico do gasto, apenas número>,
  "estabelecimento": "<nome do lugar onde foi o gasto, se mencionado>",
  "categoria_sugerida": "<categoria: Alimentação fora de casa, Supermercado, Transporte, Saúde, Lazer, Compras, Contas, Outros>",
  "descricao": "<breve descrição do gasto>",
  "metodo_pagamento": "<forma de pagamento mencionada: pix, dinheiro, débito, crédito, ou null se não mencionado>"
}}

Regras:
- Se não conseguir identificar o valor, retorne null
- Para estabelecimento, use o nome exato mencionado ou "Não especificado"
- Para categoria, analise o contexto do gasto e sugira a mais apropriada
- A descrição deve ser um resumo curto do gasto
- Se não mencionar forma de pagamento, use null

Exemplos:
- "Gastei 100 reais no supermercado" → valor: 100, estabelecimento: "Supermercado"
- "Paguei 50 de Uber" → valor: 50, estabelecimento: "Uber", categoria: "Transporte"
- "Almocei no restaurante, 45 reais" → valor: 45, estabelecimento: "Restaurante", categoria: "Alimentação fora de casa"

Retorne APENAS o JSON, sem texto adicional.
"""

            response = self.model.generate_content(prompt)

            # Limpa a resposta
            response_text = response.text.strip()
            logger.info(f"Resposta bruta do Gemini (texto): {response_text}")

            # Remove possíveis markdown code blocks
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                if lines[0].startswith('```json'):
                    response_text = '\n'.join(lines[1:-1])
                else:
                    response_text = '\n'.join(lines[1:-1])

            logger.info(f"JSON limpo (texto): {response_text}")
            dados = json.loads(response_text)

            # Valida e formata os dados
            return self._validar_dados(dados)

        except Exception as e:
            import traceback
            logger.error(f"Erro ao processar texto: {e}")
            logger.error(f"Traceback completo:\n{traceback.format_exc()}")
            return None
