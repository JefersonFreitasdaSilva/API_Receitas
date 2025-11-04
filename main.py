from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from collections import defaultdict
from typing import List, Dict, Any
import socket

app = Flask(__name__)
CORS(app)  # Permite acesso de outros computadores

# ===========================
# CONTEXTO GLOBAL (ÚNICO)
# ===========================
CONTEXTO_ATUAL = None  # <-- Aqui fica o contexto temporário


# ===========================
# Carrega JSON na memória
# ===========================
def carregar_receitas():
    try:
        with open('receitas_completo.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: Arquivo receitas_completo.json não encontrado!")
        return []
    except json.JSONDecodeError as e:
        print(f"Warning: Erro ao decodificar JSON: {e}")
        return []

RECEITAS = carregar_receitas()


# ===========================
# Funções auxiliares
# ===========================
def buscar_receita_por_id(receita_id: int) -> Dict[str, Any]:
    """Busca receita pelo ID"""
    for receita in RECEITAS:
        if receita['IdReceita'] == receita_id:
            return receita
    return None


def somar_ingredientes(lista_receitas: List[Dict]) -> List[Dict]:
    """Soma quantidades de ingredientes iguais"""
    ingredientes_somados = defaultdict(float)
    for receita in lista_receitas:
        for ing in receita.get('Ingredientes', []):
            nome = ing['NomeIngrediente']
            qtd = float(ing['Quantidade'])
            ingredientes_somados[nome] += qtd
    return [
        {'NomeIngrediente': nome, 'QuantidadeTotal': round(qtd, 2)}
        for nome, qtd in sorted(ingredientes_somados.items())
    ]


def somar_macros(lista_receitas: List[Dict]) -> Dict[str, Any]:
    """Soma macronutrientes e calorias de várias receitas"""
    macros_somados = defaultdict(float)
    calorias_total = 0
    for receita in lista_receitas:
        calorias_total += float(receita.get('CaloriasTotais', 0))
        for macro in receita.get('Macronutrientes', []):
            tipo = macro['Tipo']
            valor = float(macro['Valor'])
            macros_somados[tipo] += valor
    macros_lista = [
        {'Tipo': tipo, 'ValorTotal': round(valor, 2)}
        for tipo, valor in sorted(macros_somados.items())
    ]
    return {
        'CaloriasTotais': round(calorias_total, 2),
        'Macronutrientes': macros_lista
    }


def obter_tags_unicas() -> List[str]:
    """Retorna lista de tags únicas"""
    tags = set()
    for receita in RECEITAS:
        tags.add(receita.get('Tag', 'Outros'))
    return sorted(list(tags))


def buscar_receitas_por_nome(termo: str) -> List[Dict]:
    """Busca receitas por nome (case-insensitive)"""
    termo_lower = termo.lower()
    return [
        receita for receita in RECEITAS
        if termo_lower in receita['NomeReceita'].lower()
    ]


# ===========================
# ROTAS DE CONTEXTO (NOVAS!)
# ===========================
@app.route('/contexto/enviar', methods=['POST'])
def enviar_contexto():
    """Recebe contexto do frontend e armazena globalmente"""
    global CONTEXTO_ATUAL
    data = request.get_json()
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400

    CONTEXTO_ATUAL = data
    print("Contexto recebido e armazenado no servidor!")
    return jsonify({
        'sucesso': True,
        'mensagem': 'Contexto salvo no servidor'
    })


@app.route('/contexto/pegar', methods=['GET'])
def pegar_contexto():
    """Retorna o contexto e o remove (uso único)"""
    global CONTEXTO_ATUAL
    if CONTEXTO_ATUAL is None:
        return jsonify({'erro': 'Nenhum contexto disponível'}), 404

    ctx = CONTEXTO_ATUAL
    CONTEXTO_ATUAL = None  # ← ESVAZIA!
    print("Contexto enviado e removido do servidor.")
    return jsonify({
        'sucesso': True,
        'dados': ctx
    })


# ===========================
# ROTAS DA API (TODAS AS ORIGINAIS)
# ===========================
@app.route('/', methods=['GET'])
def home():
    """Documentação da API"""
    return jsonify({
        'mensagem': 'API de Receitas Namu',
        'total_receitas': len(RECEITAS),
        'endpoints': {
            'GET /receitas': 'Lista todas as receitas',
            'GET /receitas/<id>': 'Busca receita por ID',
            'GET /receitas/tag/<tag>': 'Filtra receitas por tag',
            'GET /receitas/buscar?nome=<termo>': 'Busca receitas por nome',
            'GET /tags': 'Lista todas as tags disponíveis',
            'POST /receitas/ingredientes': 'Ingredientes de várias receitas (soma iguais)',
            'POST /receitas/macros': 'Soma calorias e macros de várias receitas',
            'GET /receitas/<id>/ingredientes': 'Ingredientes de uma receita',
            'GET /receitas/<id>/macros': 'Macros de uma receita',
            'GET /receitas/<id>/restricoes': 'Restrições de uma receita',
            'GET /stats': 'Estatísticas gerais',
            'POST /contexto/enviar': 'Envia contexto (uso único)',
            'GET /contexto/pegar': 'Recupera contexto e remove'
        }
    })


@app.route('/receitas', methods=['GET'])
def listar_receitas():
    """Lista todas as receitas"""
    return jsonify({
        'total': len(RECEITAS),
        'receitas': RECEITAS
    })


@app.route('/receitas/<int:receita_id>', methods=['GET'])
def obter_receita(receita_id):
    """Busca receita por ID"""
    receita = buscar_receita_por_id(receita_id)
    if receita:
        return jsonify(receita)
    return jsonify({'erro': 'Receita não encontrada'}), 404


@app.route('/receitas/tag/<tag>', methods=['GET'])
def filtrar_por_tag(tag):
    """Filtra receitas por tag"""
    receitas_filtradas = [r for r in RECEITAS if r.get('Tag', '').lower() == tag.lower()]
    return jsonify({
        'tag': tag,
        'total': len(receitas_filtradas),
        'receitas': receitas_filtradas
    })


@app.route('/receitas/buscar', methods=['GET'])
def buscar_por_nome():
    """Busca receitas por nome"""
    termo = request.args.get('nome', '')
    if not termo:
        return jsonify({'erro': 'Parâmetro "nome" é obrigatório'}), 400
    receitas_encontradas = buscar_receitas_por_nome(termo)
    return jsonify({
        'termo_busca': termo,
        'total': len(receitas_encontradas),
        'receitas': receitas_encontradas
    })


@app.route('/tags', methods=['GET'])
def listar_tags():
    """Lista todas as tags disponíveis"""
    tags = obter_tags_unicas()
    contagem = {tag: sum(1 for r in RECEITAS if r.get('Tag') == tag) for tag in tags}
    return jsonify({
        'tags': tags,
        'contagem_por_tag': contagem
    })


@app.route('/receitas/<int:receita_id>/ingredientes', methods=['GET'])
def obter_ingredientes(receita_id):
    """Ingredientes de uma receita específica"""
    receita = buscar_receita_por_id(receita_id)
    if not receita:
        return jsonify({'erro': 'Receita não encontrada'}), 404
    return jsonify({
        'IdReceita': receita_id,
        'NomeReceita': receita['NomeReceita'],
        'Ingredientes': receita.get('Ingredientes', [])
    })


@app.route('/receitas/<int:receita_id>/macros', methods=['GET'])
def obter_macros(receita_id):
    """Macronutrientes de uma receita específica"""
    receita = buscar_receita_por_id(receita_id)
    if not receita:
        return jsonify({'erro': 'Receita não encontrada'}), 404
    return jsonify({
        'IdReceita': receita_id,
        'NomeReceita': receita['NomeReceita'],
        'CaloriasTotais': receita.get('CaloriasTotais'),
        'Macronutrientes': receita.get('Macronutrientes', [])
    })


@app.route('/receitas/<int:receita_id>/restricoes', methods=['GET'])
def obter_restricoes(receita_id):
    """Restrições alimentares de uma receita"""
    receita = buscar_receita_por_id(receita_id)
    if not receita:
        return jsonify({'erro': 'Receita não encontrada'}), 404
    return jsonify({
        'IdReceita': receita_id,
        'NomeReceita': receita['NomeReceita'],
        'Restricoes': receita.get('Restricoes', [])
    })


@app.route('/receitas/ingredientes', methods=['POST'])
def ingredientes_multiplas_receitas():
    """Soma ingredientes de várias receitas"""
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'erro': 'Body deve conter "ids": [...]'}), 400

    ids = data['ids']
    receitas_encontradas = [buscar_receita_por_id(rid) for rid in ids]
    receitas_encontradas = [r for r in receitas_encontradas if r]

    if not receitas_encontradas:
        return jsonify({'erro': 'Nenhuma receita encontrada com os IDs fornecidos'}), 404

    ingredientes_totais = somar_ingredientes(receitas_encontradas)
    return jsonify({
        'receitas_ids': ids,
        'receitas_nomes': [r['NomeReceita'] for r in receitas_encontradas],
        'total_receitas': len(receitas_encontradas),
        'ingredientes_somados': ingredientes_totais
    })


@app.route('/receitas/macros', methods=['POST'])
def macros_multiplas_receitas():
    """Soma macros e calorias de várias receitas"""
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'erro': 'Body deve conter "ids": [...]'}), 400

    ids = data['ids']
    receitas_encontradas = [buscar_receita_por_id(rid) for rid in ids]
    receitas_encontradas = [r for r in receitas_encontradas if r]

    if not receitas_encontradas:
        return jsonify({'erro': 'Nenhuma receita encontrada com os IDs fornecidos'}), 404

    macros_totais = somar_macros(receitas_encontradas)
    return jsonify({
        'receitas_ids': ids,
        'receitas_nomes': [r['NomeReceita'] for r in receitas_encontradas],
        'total_receitas': len(receitas_encontradas),
        'resultados': macros_totais
    })


@app.route('/stats', methods=['GET'])
def estatisticas():
    """Estatísticas gerais do sistema"""
    total_ingredientes = sum(len(r.get('Ingredientes', [])) for r in RECEITAS)
    tags = obter_tags_unicas()
    return jsonify({
        'total_receitas': len(RECEITAS),
        'total_ingredientes_registros': total_ingredientes,
        'total_tags': len(tags),
        'tags_disponiveis': tags,
        'receita_mais_calorica': max(RECEITAS, key=lambda r: r.get('CaloriasTotais', 0), default=None),
        'receita_menos_calorica': min(RECEITAS, key=lambda r: r.get('CaloriasTotais', 0), default=None)
    })


# ===========================
# Obter IP da máquina
# ===========================
def obter_ip_local():
    """Retorna o IP local da máquina"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


# ===========================
# Inicializa servidor
# ===========================
if __name__ == '__main__':
    ip_local = obter_ip_local()
    porta = 5000
    print("=" * 70)
    print(f"API iniciada com {len(RECEITAS)} receitas!")
    print("=" * 70)
    print(f"\nACESSE A API EM:\n")
    print(f" Local: http://localhost:{porta}")
    print(f" Rede: http://{ip_local}:{porta}")
    print(f"\nDocumentação: http://{ip_local}:{porta}/")
    print("\n" + "=" * 70)
    print("ENDPOINTS DE CONTEXTO:")
    print(" POST /contexto/enviar  → salva contexto")
    print(" GET  /contexto/pegar   → lê e remove contexto")
    print("\n" + "=" * 70)
    print("CONFIGURE NO FRONTEND:")
    print("=" * 70)
    print(f"\nconst API_BASE_URL = 'http://{ip_local}:{porta}';")
    print("\n" + "=" * 70 + "\n")
    app.run(host='0.0.0.0', port=porta, debug=True)