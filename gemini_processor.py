"""
Módulo para processar imagens de comprovantes usando Google Gemini
"""
import google.generativeai as genai
from PIL import Image
import json
from datetime import datetime


class ComprovanteProcessor:
    """Processa comprovantes usando Gemini Vision"""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

        # Lista modelos disponíveis e prioriza os flash (mais baratos/gratuitos)
        print("Listando modelos disponíveis...")
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
                    print(f"  - {m.name}")
        except Exception as e:
            print(f"Erro ao listar modelos: {e}")

        # Prioriza modelos flash que têm melhor tier gratuito
        priority_keywords = ['flash', 'lite', 'exp']
        flash_models = [m for m in available_models if any(kw in m.lower() for kw in priority_keywords)]

        # Se não encontrar flash, usa qualquer um
        models_to_try = flash_models if flash_models else available_models

        # Tenta usar o primeiro modelo disponível
        if models_to_try:
            # Remove o prefixo 'models/' se existir
            model_name = models_to_try[0].replace('models/', '')
            self.model = genai.GenerativeModel(model_name)
            print(f"\n[OK] Usando modelo: {model_name}")
        else:
            raise Exception("Nenhum modelo Gemini disponível. Verifique sua API Key.")

    def processar_comprovante(self, image_path: str) -> dict:
        """
        Processa imagem do comprovante e extrai informações

        Returns:
            dict com: valor, estabelecimento, data, categoria_sugerida
        """
        img = None
        try:
            img = Image.open(image_path)

            prompt = """
Analise este comprovante de pagamento e extraia as seguintes informações em formato JSON:

{
  "valor": <valor numérico da compra, apenas número>,
  "estabelecimento": "<nome do estabelecimento/comerciante>",
  "data": "<data da transação no formato YYYY-MM-DD>",
  "categoria_sugerida": "<categoria sugerida: Alimentação fora de casa, Supermercado, Transporte, Saúde, Lazer, Compras, Contas, Outros>"
}

Regras:
- Se não conseguir identificar algum campo, use null
- Para categoria, analise o tipo de estabelecimento e sugira a mais apropriada
- Para valor, extraia apenas o número (ex: 45.90, não R$ 45,90)
- Se houver múltiplos valores, use o valor total da transação

Retorne APENAS o JSON, sem texto adicional.
"""

            response = self.model.generate_content([prompt, img])

            # Limpa a resposta para garantir que é JSON válido
            response_text = response.text.strip()

            # Remove possíveis markdown code blocks
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])

            dados = json.loads(response_text)

            # Valida e formata os dados
            return self._validar_dados(dados)

        except Exception as e:
            print(f"Erro ao processar comprovante: {e}")
            return None
        finally:
            # Fecha a imagem para liberar o arquivo
            if img:
                img.close()

    def _validar_dados(self, dados: dict) -> dict:
        """Valida e formata os dados extraídos"""
        resultado = {
            'valor': None,
            'estabelecimento': None,
            'data': None,
            'categoria_sugerida': 'Outros'
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

        # Valida data
        if 'data' in dados and dados['data']:
            try:
                resultado['data'] = datetime.strptime(dados['data'], '%Y-%m-%d')
            except (ValueError, TypeError):
                resultado['data'] = datetime.now()
        else:
            resultado['data'] = datetime.now()

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

        return resultado

    def categorizar_estabelecimento(self, estabelecimento: str, categorias_disponiveis: list) -> str:
        """
        Usa IA para categorizar um estabelecimento baseado nas categorias disponíveis
        """
        if not categorias_disponiveis:
            return None

        prompt = f"""
Dado o estabelecimento "{estabelecimento}", escolha a categoria mais apropriada da lista abaixo:

{', '.join(categorias_disponiveis)}

Retorne APENAS o nome da categoria, sem texto adicional.
"""

        try:
            response = self.model.generate_content(prompt)
            categoria = response.text.strip()

            # Verifica se a categoria retornada está na lista
            if categoria in categorias_disponiveis:
                return categoria
        except Exception as e:
            print(f"Erro ao categorizar: {e}")

        return None
