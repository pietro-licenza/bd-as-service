import requests
import json
import re
from bs4 import BeautifulSoup

def fetch_and_parse_decathlon(url):
    print(f"\n🚀 Acessando: {url}")
    
    # Headers para simular um navegador real e evitar bloqueios
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Garante que a página carregou (Erro 200)
        html_content = response.text
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            "Título": "",
            "Marca": "",
            "EAN": "Não disponível",
            "Preço": 0.0,
            "URLs": [],
            "Link_Original": url
        }

        # 1. DADOS BÁSICOS (JSON-LD)
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                temp_json = json.loads(script.string)
                if isinstance(temp_json, dict) and temp_json.get('@type') == 'Product':
                    result["Título"] = temp_json.get('name', '')
                    result["Marca"] = temp_json.get('brand', {}).get('name', '') if isinstance(temp_json.get('brand'), dict) else temp_json.get('brand', '')
                    
                    imgs = temp_json.get('image', [])
                    result["URLs"] = (imgs if isinstance(imgs, list) else [imgs])[:10]
                    
                    offers = temp_json.get('offers', {})
                    p_now = float(offers.get('price', 0) or offers.get('lowPrice', 0))
                    p_old = float(offers.get('highPrice', 0))
                    result["Preço"] = max(p_now, p_old)
                    break
            except: continue

        # 2. CAPTURA DO EAN (Lógica Cirúrgica v17)
        # Estratégia A: Busca pela classe técnica escapada (o "pulo do gato")
        ean_regex = r'technical-description\\?\">(\d{13})'
        match = re.search(ean_regex, html_content)
        
        if match:
            result["EAN"] = match.group(1)
        else:
            # Estratégia B: Busca pelo rótulo literal no texto
            fallback_regex = r'Códigos EAN13 do produto.*?(\d{13})'
            match_fallback = re.search(fallback_regex, html_content, re.DOTALL)
            if match_fallback:
                result["EAN"] = match_fallback.group(1)

        return result

    except Exception as e:
        return {"URL": url, "Erro": f"Falha ao acessar: {str(e)}"}

if __name__ == "__main__":
    # --- INSIRA AS 3 URLs AQUI ---
    urls_para_testar = [
        "https://www.decathlon.com.br/barraca-de-camping-4-2-arpenaz-4-pessoas-2-quartos-azul-8562098-quechua/p",
        "https://www.decathlon.com.br/mochila-de-desporto-com-compartimento-para-calcado-17l-preto-8928422-decathlon/p"
    ]

    final_results = []
    for url in urls_para_testar:
        dados = fetch_and_parse_decathlon(url)
        final_results.append(dados)
        print(json.dumps(dados, indent=2, ensure_ascii=False))

    # Salva o resultado final em um arquivo JSON para sua conferência
    with open("resultado_decathlon.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, indent=2, ensure_ascii=False)
    print("\n✅ Processo finalizado! Resultados salvos em 'resultado_decathlon.json'")