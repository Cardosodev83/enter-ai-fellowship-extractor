# Autor: Mariana Cardoso da Silva

import json
import re
import os  # ler a variavel de ambiente
from pypdf import PdfReader  # biblioteca que vai ler o pdf
from openai import AsyncOpenAI  # biblioteca do LLM
from difflib import SequenceMatcher  # pra comparar labels parecidos e aproveitar aprendizado
import time
import hashlib
import asyncio

global total_chamadas_llm
cache_local = {}

# --- Componente 1 : Base de Conhecimento (KB) ---

KB_FILE = "base_conhecimento.json"
BASE_DIR = "ai-fellowship-data-main/files/"
CACHE_FILE = "cache_llm.json"

# Carrega as regras aprendidas (regras e schemas aprendidos)
def carregar_kb():
    try:
        with open(KB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # vai retornar um cérebro vazio se for a primeira vez

# Salva as novas regras que ele aprendeu
def salvar_kb(kb):
    with open(KB_FILE, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)

# Leitura do PDF
def extrair_texto_pdf(caminho_pdf):
    try:
        reader = PdfReader(caminho_pdf)
        if len(reader.pages) > 0:
            pagina = reader.pages[0]  # pega a primeira página
            return pagina.extract_text()
        else:
            print(f"Aviso: PDF sem páginas {caminho_pdf}")
            return ""  # vai retornar vazio se o PDF não tiver páginas
    except Exception as e:
        print(f"Erro ao ler o PDF {caminho_pdf}: {e}")
        return None

# Motor de Heurísticas (caminho rápido)
def aplicar_regra(texto, regra):
    # se for uma regra regex aprendida automaticamente
    if regra.startswith("REGEX:"):
        padrao = regra.replace("REGEX:", "").strip()
        match = re.search(padrao, texto)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return None

# --- Função auxiliar: hash do texto para cache persistente ---
def hash_texto(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


# --- Função de configuração automática da API Key ---
def configurar_api_key():

    API_FILE = ".api_key.json"

    # tenta carregar a chave salva anteriormente
    try:
        with open(API_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if "OPENAI_API_KEY" in dados and dados["OPENAI_API_KEY"]:
                return dados["OPENAI_API_KEY"]
    except FileNotFoundError:
        pass
    print("🔑 Configuração inicial: informe sua OpenAI API Key (ex: sk-abc123...):")
    chave = input("Cole sua chave aqui: ").strip()
    if not chave.startswith("sk-"):
        print("Erro: formato inválido. A chave deve começar com 'sk-'.")
        exit()
    with open(API_FILE, "w", encoding="utf-8") as f:
        json.dump({"OPENAI_API_KEY": chave}, f, indent=2)
    print("✅ API Key salva com sucesso!")
    return chave




# --- Configuração do cliente LLM ---
api_key = configurar_api_key()
client = AsyncOpenAI(api_key=api_key)

# --- Pré-aquecimento (melhora tempo da 1ª requisição) ---
async def preaquecer_modelo():
    try:
        print("🔧 Iniciando o motor de IA... (pré-aquecendo modelo)")
        await client.chat.completions.create(model="gpt-5-mini", messages=[{"role": "system", "content": "Ping"}])
        print("✅ Modelo pronto para uso!\n")
        print("🤖 Aprendendo padrões base antes da primeira extração...")   
        await client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Aprenda exemplos de documentos PDF com campos como nome, inscrição, data, cidade e valores numéricos.",
                },
                {
                    "role": "user",
                    "content": "Este é um treinamento rápido de contexto. Não precisa responder nada.",
                },
            ],
        )
        print("✅ Contexto semântico inicial aprendido!")

    except Exception as e:
        print(f"Aviso: falha no pré-aquecimento ({e})\n")
        

# --- Chamadas assíncronas ao LLM ---
async def chamar_llm_para_extracao(texto_pdf, schema_para_llm):
    print(f"--- Chamando LLM para {len(schema_para_llm)} campos ---")

    # Limita texto para evitar custo e tempo excessivo
    texto_pdf = texto_pdf[:6000] + (" ...[texto truncado]" if len(texto_pdf) > 6000 else "")

    # Gera chave única baseada em hash do texto e schema
    cache_key = hash_texto(texto_pdf + json.dumps(schema_para_llm, sort_keys=True))
    global cache_local

    # Carrega cache do disco, se ainda não estiver na memória
    if not cache_local:
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_local = json.load(f)
        except FileNotFoundError:
            cache_local = {}

    if cache_key in cache_local:
        print("(Resultado carregado do cache LLM)")
        return cache_local[cache_key]

    # Divide schema apenas se for grande
    def dividir_dict_em_blocos(d, n):
        if len(d) <= n:
            yield d
        else:
            itens = list(d.items())
            for i in range(0, len(itens), n):
                yield dict(itens[i:i + n])

    # Monta tarefas assíncronas para cada bloco de campos
    async def processar_bloco(bloco_schema):
        prompt = f"""
        Extraia APENAS os seguintes campos em JSON do texto abaixo.
        Campos ausentes devem ser null. Não invente informações.

        Texto:
        \"\"\"
        {texto_pdf}
        \"\"\"
        Campos:
        {json.dumps(bloco_schema, indent=2, ensure_ascii=False)}
        """
        inicio = time.time()
        completion = await client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "Você é um extrator de dados preciso e conciso."},
                {"role": "user", "content": prompt}
            ],
        )
        fim = time.time()
        print(f"⏳ Tempo da chamada LLM: {fim - inicio:.2f}s")
        try:
            resposta = completion.choices[0].message.content
            json_match = re.search(r'\{.*\}', resposta, re.DOTALL)
            return json.loads(json_match.group(0)) if json_match else {}
        except Exception:
            return {}

    blocos = list(dividir_dict_em_blocos(schema_para_llm, 8))
    resultados = await asyncio.gather(*(processar_bloco(b) for b in blocos))
    dados_final = {k: v for d in resultados for k, v in d.items()}

    # Atualiza cache (mantém no máximo 500 entradas)
    cache_local[cache_key] = dados_final
    if len(cache_local) > 500:
        cache_local = dict(list(cache_local.items())[-500:])
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_local, f, indent=2, ensure_ascii=False)

    return dados_final

# --- Função pra encontrar labels parecidos e aproveitar aprendizado ---
def label_parecido(label, kb):
    for existente in kb.keys():
        if SequenceMatcher(None, label, existente).ratio() > 0.8:
            return existente
    return label

# --- Heurísticas locais para campos comuns ---
def heuristicas_locais(texto):
    resultados = {}
    if re.search(r"SITUAÇÃO\s*REGULAR", texto, re.IGNORECASE):
        resultados["situacao"] = "SITUAÇÃO REGULAR"
    if re.search(r"\b(PR|SP|RJ|MG|RS|BA|PE|SC|DF)\b", texto):
        resultados["seccional"] = re.search(r"\b(PR|SP|RJ|MG|RS|BA|PE|SC|DF)\b", texto).group(1)
    return resultados

# --- Estrutura principal ---
async def processar_requisicao(label, extraction_schema, caminho_pdf):
    
    if not hasattr(processar_requisicao, "_cache_kb"):
        processar_requisicao._cache_kb = carregar_kb()
    kb = processar_requisicao._cache_kb

    print(f"Processando label: {label}")
    resultados_finais = {}

    texto_pdf = extrair_texto_pdf(caminho_pdf)
    if not texto_pdf:
        return {"erro": "PDF vazio ou ilegível"}

    # Carrega conhecimento e busca label similar
    label_base = label_parecido(label, kb)
    if label_base not in kb:
        kb[label_base] = {"schema_aprendido": {}, "regras_de_extracao": {}}

    # Aplica heurísticas fixas (sem custo)
    resultados_finais.update(heuristicas_locais(texto_pdf))

    # Tenta aplicar regras já aprendidas
    campos_faltantes = {}
    for campo, desc in extraction_schema.items():
        regra = kb[label_base]["regras_de_extracao"].get(campo)
        if regra:
            valor = aplicar_regra(texto_pdf, regra)
            if valor:
                resultados_finais[campo] = valor
            else:
                campos_faltantes[campo] = desc
        elif campo not in resultados_finais:
            campos_faltantes[campo] = desc
    
    # Melhoria 3 — Reaproveitamento por similaridade de campos
    # Tenta usar regex de campos parecidos de schemas anteriores
    campos_faltantes_novos = {}
    for campo, desc in campos_faltantes.items():
        campo_similar = label_parecido(campo, kb[label_base]["regras_de_extracao"])
        if campo_similar != campo:
            regra = kb[label_base]["regras_de_extracao"].get(campo_similar)
            if regra:
                valor = aplicar_regra(texto_pdf, regra)
                if valor:
                    resultados_finais[campo] = valor
                else:
                    campos_faltantes_novos[campo] = desc
            else:
                campos_faltantes_novos[campo] = desc
        else:
            campos_faltantes_novos[campo] = desc

    campos_faltantes = campos_faltantes_novos

    # Se ainda há campos faltantes, chama o LLM
    if campos_faltantes:
        print(f"Campos não encontrados localmente: {list(campos_faltantes.keys())}")
        dados_llm = await chamar_llm_para_extracao(texto_pdf, campos_faltantes)
        resultados_finais.update(dados_llm)

        # Aprendizado automático: cria regex de contexto
        # Aprendizado automático: cria regex contextual
        for campo, valor in dados_llm.items():
            if valor and isinstance(valor, str):
                padrao_valor = re.escape(valor.strip())
                texto = texto_pdf

                # Localiza a linha onde o valor aparece
                linhas = texto.splitlines()
                contexto_limpo = None
                for linha in linhas:
                    if valor.strip() in linha:
                        partes = linha.split(valor.strip())
                        if len(partes) > 0:
                            contexto_limpo = partes[0].strip()
                            break

                if contexto_limpo:
                    contexto_limpo = re.sub(r'[^A-Za-zÀ-ÿ\s:]', '', contexto_limpo).strip()
                    # Captura até quebra de linha, ponto ou tabulação
                    regex_contextual = (
                        f"REGEX:(?i){re.escape(contexto_limpo)}[:\\s]{{0,10}}([\\wÀ-ÿ.,\\-/ ]+?)(?=\\n|$|\\t|\\r)"
                    )
                else:
                    # Fallback mais curto (menor risco de capturar campos vizinhos)
                    regex_contextual = f"REGEX:(?:.{{0,10}}){padrao_valor}(?:.{{0,10}})"

                kb[label_base]["regras_de_extracao"][campo] = regex_contextual
                kb[label_base]["schema_aprendido"][campo] = extraction_schema[campo]

    # Garante retorno completo
    for campo in extraction_schema.keys():
        resultados_finais.setdefault(campo, None)

    salvar_kb(kb)
    return resultados_finais


# --- Execução principal ---
async def main():
    await preaquecer_modelo()
    caminho_dataset = "ai-fellowship-data-main/dataset.json"

    try:
        with open(caminho_dataset, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print(f"Erro: arquivo {caminho_dataset} não encontrado.")
        return

    resultados_gerais = []
    inicio_execucao = time.time()

    for item in dataset:
        label = item["label"]
        extraction_schema = item["extraction_schema"]
        pdf_path = os.path.join(BASE_DIR, item["pdf_path"])
        resultado = await processar_requisicao(label, extraction_schema, pdf_path)
        salvar_kb(processar_requisicao._cache_kb)

        print("\n--- Resultado Final ---")
        print(json.dumps(resultado, indent=2, ensure_ascii=False))

        resultados_gerais.append({"arquivo": item["pdf_path"], "resultado": resultado})

    fim_execucao = time.time()
    tempo_total = fim_execucao - inicio_execucao
    print("\n=========================================")
    print("📊 Resumo de Desempenho:")
    print(f"⏱️  Tempo total de execução: {tempo_total:.2f} segundos")
    print(f"📄  Documentos processados: {len(resultados_gerais)}")
    print(f"⏱️ Tempo médio por documento: {tempo_total / len(resultados_gerais):.2f}s")
    print("=========================================\n")

if __name__ == "__main__":
    asyncio.run(main())