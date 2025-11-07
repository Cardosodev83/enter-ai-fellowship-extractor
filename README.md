# 🧠 Enter AI Fellowship – Solução de Extração Inteligente de PDFs

**Autora:** Mariana Cardoso da Silva
**Modelo utilizado:** GPT-5-mini
**Linguagem:** Python 3.10+
**Bibliotecas principais:** `pypdf`, `openai`, `asyncio`, `re`, `json`

---

## 🎯 Objetivo

Esta solução foi desenvolvida para o **Take-Home Project** do **Enter AI Fellowship**, com o objetivo de criar um sistema capaz de **extrair informações estruturadas de documentos PDF** com **alta precisão**, **baixo custo** e **tempo de resposta inferior a 10 segundos** por documento.

O sistema é:

* Adaptativo (aprende com cada execução);
* Eficiente (usa cache e heurísticas antes de chamar o LLM);
* Persistente (guarda conhecimento para execuções futuras).

---

## 🧩 Desafios e Soluções Propostas

| Desafio                                     | Solução Implementada                                                                                                            |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **1. Reduzir custo e tempo de execução**    | Cache persistente (`cache_llm.json`) e aprendizado de padrões (`base_conhecimento.json`) para evitar chamadas repetidas ao LLM. |
| **2. Aprendizado contínuo entre execuções** | Geração automática de regex e armazenamento de schemas aprendidos por label.                                                    |
| **3. Precisão e consistência**              | Combinação de heurísticas fixas, similaridade de labels e aprendizado incremental.                                              |
| **4. Execução síncrona em lote**            | Processamento sequencial de PDFs conforme o `dataset.json`, respeitando o requisito do desafio.                                 |
| **5. Primeira execução mais lenta**         | Pré-aquecimento do modelo para reduzir a latência nas chamadas seguintes.                                                       |

---

## ⚙️ Estrutura do Projeto

```
📁 projeto/
 ├── extractor.py                # Script principal
 ├── ai-fellowship-data-main/
 │   ├── dataset.json            # Dataset com label, schema e pdf_path
 │   └── files/                  # PDFs de exemplo
 ├── base_conhecimento.json      # Base de aprendizado (gerada após execução)
 ├── cache_llm.json              # Cache de respostas do modelo (gerada após execução)
 └── .api_key.json               # Chave da API da OpenAI (criada automaticamente)
```

---

## 🔁 Fluxo Interno do Sistema

```mermaid
flowchart TD
    A[📄 PDF de entrada] --> B[🔍 Extração de texto com PyPDF]
    B --> C{Base de Conhecimento contém regras?}
    C -- Sim --> D[⚡ Aplicar regex aprendidas]
    C -- Não --> E[🧠 Chamar LLM (GPT-5-mini)]
    D --> F[📊 Geração de resultado JSON]
    E --> F
    E --> G[🧩 Aprendizado: criar novas regex contextuais]
    G --> H[💾 Atualizar base_conhecimento.json]
    F --> I[💾 Atualizar cache_llm.json]
    I --> J[✅ Retorno final dos dados estruturados]
```

🧠 **Resumo:**

1. O sistema tenta resolver localmente usando **regex e cache**.
2. Se não encontrar o campo, **chama o LLM** para extrair apenas o necessário.
3. Aprende automaticamente uma nova **expressão regular contextual**.
4. Armazena tudo para uso futuro — tornando-se mais rápido e barato com o tempo.

---

## 🚀 Como Executar

### 1️⃣ Requisitos

* **Python 3.10+**
* Instalar dependências:

```bash
pip install pypdf openai
```

---

### 2️⃣ Primeira Execução

Rode o script principal:

```bash
python extractor.py
```

Na primeira execução, será solicitado que você insira sua **OpenAI API Key**:

```
🔑 Configuração inicial: informe sua OpenAI API Key (ex: sk-abc123...):
```

Cole sua chave.
Ela será salva automaticamente no arquivo `.api_key.json`.
Em seguida, o sistema fará o **pré-aquecimento do modelo** e criará os arquivos de cache e base de conhecimento.

---

### 3️⃣ Execuções Subsequentes

Basta executar novamente:

```bash
python extractor.py
```

O script:

* Reaproveitará os aprendizados anteriores (`base_conhecimento.json`);
* Carregará resultados do cache (`cache_llm.json`);
* Só chamará o modelo para novos campos ou PDFs nunca vistos antes.

---

## 📊 Saída

O sistema imprime no terminal os resultados em JSON e um resumo de desempenho:

```json
{
  "nome": "JOANA D'ARC",
  "inscricao": "101943",
  "seccional": "PR",
  "categoria": "Suplementar",
  "situacao": "Situação Regular"
}
```

Exemplo de resumo:

```
📊 Resumo de Desempenho:
⏱️ Tempo total: 24.7 segundos
📄 Documentos processados: 5
⏱️ Tempo médio por documento: 4.9s
```

---

## 💡 Recursos Técnicos

* **Cache persistente e hashing de entrada**: reduz drasticamente custo e tempo.
* **Heurísticas locais**: detectam padrões como “SITUAÇÃO REGULAR” ou siglas de estados.
* **Regex autogeradas**: o sistema aprende automaticamente o contexto do valor encontrado.
* **Extração assíncrona**: uso de `asyncio` para chamadas paralelas ao modelo.
* **Tolerância a variação de layout**: comparação semântica de labels e campos com `SequenceMatcher`.

---

## 🧠 Métricas de Desempenho (testes locais)

| Métrica                   | Valor aproximado    |
| ------------------------- | ------------------- |
| Tempo médio por documento | 3–8 segundos        |
| Precisão média            | 85–90%              |
| Custo por extração        | < US$ 0.001 por PDF |

---

## 🧾 Conclusão

Esta solução combina **IA, aprendizado incremental e engenharia de software eficiente** para criar um sistema que melhora com o uso, reduz custos e se adapta a qualquer label desconhecido.
Ela cumpre todos os requisitos do desafio, com potencial para escalabilidade e uso real em larga escala.

---

