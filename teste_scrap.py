"""
Debug: Leroy Merlin /api/v3/products/{id}/sellers

Estrategia:
  1. Primeiro busca as lojas reais via /api/v1/stores (endpoint publico)
  2. Pega IDs reais e testa o /sellers com eles
  3. Testa variacoes de x-assisted-sale para resolver o 422
"""

from curl_cffi import requests
import json

PRODUTO_ID = "90602526"

BASE_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer":         "https://www.leroymerlin.com.br/",
    "Origin":          "https://www.leroymerlin.com.br",
    "x-device":        "desktop",
    "x-datadog-origin": "rum",
}


def buscar_lojas():
    """Busca lojas reais pela API publica de stores."""
    endpoints = [
        "https://www.leroymerlin.com.br/api/v1/stores",
        "https://www.leroymerlin.com.br/api/v2/stores",
        "https://www.leroymerlin.com.br/api/v3/stores",
        "https://www.leroymerlin.com.br/api/v1/stores?region=grande_sao_paulo",
        "https://www.leroymerlin.com.br/api/v3/regions",
        "https://www.leroymerlin.com.br/api/v1/regions",
    ]
    print("\n=== BUSCANDO LOJAS REAIS ===")
    for url in endpoints:
        try:
            r = requests.get(url, headers=BASE_HEADERS, impersonate="chrome124", timeout=10)
            print(f"  {r.status_code} | {url}")
            if r.status_code == 200:
                data = r.json()
                print(f"    Resposta: {json.dumps(data)[:400]}")
                return data
        except Exception as e:
            print(f"  EXC | {url} -> {e}")
    return None


def testar_sellers(store_id, assisted_sale, region="grande_sao_paulo"):
    url = f"https://www.leroymerlin.com.br/api/v3/products/{PRODUTO_ID}/sellers"
    headers = {
        **BASE_HEADERS,
        "x-region":        region,
        "x-store":         str(store_id),
        "x-assisted-sale": str(assisted_sale),
    }
    try:
        r = requests.get(url, headers=headers, params={"store": store_id},
                         impersonate="chrome124", timeout=12)
        if r.status_code == 200:
            data = r.json()
            sellers = data.get("data", [])
            if sellers:
                pricing = sellers[0].get("pricing", {})
                print(f"  [OK] store={store_id} assisted_sale={assisted_sale}")
                print(f"       pricing: {pricing}")
                return True
            else:
                print(f"  [WARN] store={store_id} -> 200 sem sellers: {data}")
        else:
            erros = r.json().get("errors", []) if "json" in r.headers.get("content-type","") else []
            codigos = [e.get("code") for e in erros]
            print(f"  [422] store={store_id} assisted={assisted_sale} -> campos invalidos: {codigos}")
    except Exception as e:
        print(f"  [EXC] store={store_id} -> {e}")
    return False


def varrer_combinacoes():
    """
    Testa combinacoes de store ID e x-assisted-sale para descobrir
    quais valores o endpoint aceita.
    """
    print("\n=== VARRENDO COMBINACOES store x assisted-sale ===")

    # Primeiro tenta sem nenhum dos dois — so para ver o status
    url = f"https://www.leroymerlin.com.br/api/v3/products/{PRODUTO_ID}/sellers"
    r = requests.get(url, headers={**BASE_HEADERS, "x-region": "grande_sao_paulo"},
                     impersonate="chrome124", timeout=10)
    print(f"  Sem x-store e sem x-assisted-sale: {r.status_code} | {r.text[:300]}")

    # Candidatos de assisted-sale
    assisted_opts = ["0", "1", "false", "true", "False", "True"]
    # Candidatos de store (range maior)
    store_ids = list(range(1, 30)) + [100, 200, 300, 400, 500, 1000, 2000]

    for assisted in assisted_opts:
        for sid in store_ids:
            ok = testar_sellers(sid, assisted)
            if ok:
                print(f"\n>>> COMBINACAO VALIDA ENCONTRADA: store={sid} x-assisted-sale={assisted} <<<")
                return sid, assisted
    print("\nNenhuma combinacao valida encontrada.")
    return None, None


def testar_sellers_sem_store():
    """
    Descoberta: sem x-store e x-assisted-sale a API ja retorna 200 com preco.
    price.from = preco cheio (sem desconto)
    price.to   = preco promocional
    """
    import json
    url = f"https://www.leroymerlin.com.br/api/v3/products/{PRODUTO_ID}/sellers"
    headers = {
        **BASE_HEADERS,
        "x-region": "grande_sao_paulo",
    }
    print(f"\n=== TESTE FINAL: sellers sem x-store ===")
    try:
        r = requests.get(url, headers=headers, impersonate="chrome124", timeout=12)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  Resposta completa: {json.dumps(data, indent=2)[:1200]}")
            sellers = data.get("data", [])
            if sellers:
                pricing = sellers[0].get("pricing", {})
                price   = pricing.get("price", {})
                print(f"\n  [RESULTADO]")
                print(f"  price.to   (promocional): R$ {price.get('to')}")
                print(f"  price.from (cheio):       R$ {price.get('from')}")
                print(f"  regionPrice:              R$ {price.get('regionPrice')}")
        else:
            print(f"  Erro: {r.text[:400]}")
    except Exception as e:
        print(f"  EXC: {e}")


if __name__ == "__main__":
    testar_sellers_sem_store()
