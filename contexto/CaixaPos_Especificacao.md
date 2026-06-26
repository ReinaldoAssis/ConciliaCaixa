# CaixaPos
## Sistema de Conciliação de Caixa — Posto de Combustível

**Documento de Especificação de Sistema**
Versão 1.0 · Junho 2026 · Auto Posto Lagoa Café

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Estrutura de Dados (TinyDB)](#2-estrutura-de-dados-tinydb)
3. [Mapeamento de Relatórios CSV / XLS](#3-mapeamento-de-relatórios-csv--xls)
4. [Telas e Módulos](#4-telas-e-módulos)
5. [Regras de Negócio](#5-regras-de-negócio)
6. [Layout e UX](#6-layout-e-ux)
7. [Arquitetura de Arquivos](#7-arquitetura-de-arquivos)
8. [Critérios de Aceite](#8-critérios-de-aceite)
9. [Dependências Python](#9-dependências-python)
- [Apêndice A — Glossário](#apêndice-a--glossário)
- [Apêndice B — Notas sobre o Arquivo Premmia](#apêndice-b--notas-sobre-o-arquivo-premmia)

---

## 1. Visão Geral

O **CaixaPos** é uma aplicação desktop desenvolvida para auxiliar no fechamento e conciliação do caixa diário de um posto de combustível. O sistema centraliza a importação automática de relatórios de diferentes fontes, consolida os valores por bandeira/forma de pagamento e apresenta um resultado comparativo entre o que foi registrado no sistema interno do posto (coluna **Sistema**) e o que foi efetivamente liquidado pelas operadoras (coluna **Site**).

### 1.1 Objetivos

- Eliminar a digitação manual de valores ao processar CSVs exportados de cada fonte.
- Consolidar bandeiras POS e SMART em uma única linha por bandeira.
- Controlar contagem física de cédulas com rastreio de notas de R$ 200.
- Manter histórico pesquisável de caixas fechados.
- Exportar relatório final em PDF para arquivo.

### 1.2 Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Interface | Python · Tkinter · ttkbootstrap (tema padrão) |
| Persistência | TinyDB (JSON local, sem servidor) |
| Distribuição | PyInstaller — executável único por plataforma |
| Exportação PDF | ReportLab (ou WeasyPrint) via módulo interno |
| Leitura de XLS | xlrd — necessário para o relatório Premmia (.xls) |
| Leitura de CSV | csv (stdlib) com detecção de encoding |

---

## 2. Estrutura de Dados (TinyDB)

O banco é um arquivo JSON local (`caixapos_db.json`) gerenciado pelo TinyDB. A estrutura utiliza duas tabelas principais.

### 2.1 Tabela `caixas`

Cada documento representa um fechamento de caixa completo.

```json
{
  "id": "uuid",
  "data": "2026-06-16",
  "criado_em": "ISO8601",
  "status": "rascunho | conciliado",
  "fitcard_total": 6646.12,
  "categorias": {
    "PAG_PIX":            { "sistema": 8631.33, "site": 8166.00 },
    "ELO_CREDITO":        { "sistema": 260.05,  "site": 259.00  },
    "ELO_DEBITO":         { "sistema": 1180.90, "site": 1177.00 },
    "MASTERCARD_CREDITO": { "sistema": 5050.91, "site": 5041.00 },
    "MASTERCARD_DEBITO":  { "sistema": 3104.73, "site": 3117.00 },
    "VISA_CREDITO":       { "sistema": 2733.26, "site": 2729.00 },
    "VISA_DEBITO":        { "sistema": 4359.63, "site": 4356.00 },
    "CARTAO_FITCARD":     { "sistema": 0.00,    "site": 6646.12 },
    "PREMMIA_CARTAO":     { "sistema": 726.97,  "site": 0.00    },
    "PREMMIA_PIX":        { "sistema": 40.00,   "site": 0.00    },
    "PREMMIA_CUPOM":      { "sistema": 2.50,    "site": 0.00    },
    "FITCARD":            { "sistema": 6646.12, "site": 0.00    }
  },
  "sangria": 9176.00,
  "notas_a_prazo": 8828.08,
  "despesas": 297.81,
  "contagens_dinheiro": [],
  "observacoes": ""
}
```

### 2.2 Sub-documento `contagem_dinheiro`

```json
{
  "id": "uuid",
  "label": "Contagem 1",
  "criado_em": "ISO8601",
  "notas": {
    "200": 0, "100": 2, "50": 3, "20": 5,
    "10": 4, "5": 2, "2": 1
  },
  "seriais_200": ["12345", "67890"],
  "moedas": 14.75,
  "total": 347.75
}
```

> `seriais_200`: lista com os últimos 5 dígitos do serial de cada nota de R$ 200 contada.

---

## 3. Mapeamento de Relatórios CSV / XLS

### 3.1 Relatório do Sistema Interno — CAIXA (CSV)

Arquivo gerado pelo sistema PDV do posto. **Delimitador:** ponto-e-vírgula (`;`). **Encoding:** Latin-1 (ISO-8859-1).

O parser deve localizar a seção `FINANCEIRO` e ler as linhas de saída a partir da linha que contém o cabeçalho `Entradas;Saídas`.

#### Regra de consolidação POS + SMART

Para uma mesma bandeira, os prefixos `POS PAGSEGURO` e `SMART PAGSEGURO` são variantes do mesmo terminal — seus valores devem ser **somados** na mesma categoria final.

| Nome no CSV | Prefixo | Categoria Final | |
|---|---|---|---|
| POS PAGSEGURO MASTER.CRE | POS | `MASTERCARD_CREDITO` | |
| SMART PAGSEGURO MASTER.C | SMART | `MASTERCARD_CREDITO` | ← soma |
| POS PAGSEGURO MASTER.DEB | POS | `MASTERCARD_DEBITO` | |
| SMART PAGSEGURO MASTER.D | SMART | `MASTERCARD_DEBITO` | ← soma |
| POS PAGSEGURO ELO DEBITO | POS | `ELO_DEBITO` | |
| SMART PAGSEGURO ELO DEBI | SMART | `ELO_DEBITO` | ← soma |
| POS PAGSEGURO VISA CREDI | POS | `VISA_CREDITO` | |
| SMART PAGSEGURO VISA CRE | SMART | `VISA_CREDITO` | ← soma |
| POS PAGSEGURO VISA DEBIT | POS | `VISA_DEBITO` | |
| SMART PAGSEGURO VISA DEB | SMART | `VISA_DEBITO` | ← soma |

#### Entradas adicionais (mapeamento direto)

| Nome no CSV | Campo Destino | Observação |
|---|---|---|
| BR PREMMIA CARTAO | `PREMMIA_CARTAO` (sistema) | Bandeira Premmia cartão |
| BR PREMMIA GENERICO / CUPOM | `PREMMIA_CUPOM` (sistema) | Cupom genérico Premmia |
| BR PREMMIA PIX | `PREMMIA_PIX` (sistema) | PIX via app Premmia |
| CARTAO FITCARD | `FITCARD` (sistema) | Cartão frota FitCard |
| PAG PIX | `PAG_PIX` (sistema) | PIX PagBank |
| SANGRIA | `sangria` | Campo separado, não entra na conciliação |
| NOTAS A PRAZO | `notas_a_prazo` | Campo separado |
| DESPESAS DO POSTO | `despesas` | Campo separado |

### 3.2 Relatório PagBank — O que vendi (CSV)

Arquivo exportado do painel PagBank. **Delimitador:** ponto-e-vírgula (`;`). **Encoding:** UTF-8 com BOM.

O parser filtra apenas registros com `Status = "Aprovada"` e agrupa pela combinação `Bandeira + Forma de Pagamento`, somando o campo **Valor Bruto**.

| Bandeira + Forma de Pagamento | Categoria Final | Observação |
|---|---|---|
| Pix (sem bandeira) | `PAG_PIX` (site) | Soma de todos os PIX aprovados |
| Visa · Débito | `VISA_DEBITO` (site) | |
| Visa · Crédito | `VISA_CREDITO` (site) | |
| Mastercard · Débito | `MASTERCARD_DEBITO` (site) | |
| Mastercard · Crédito | `MASTERCARD_CREDITO` (site) | |
| Elo · Débito | `ELO_DEBITO` (site) | |
| Elo · Crédito | `ELO_CREDITO` (site) | |

### 3.3 Relatório Premmia (XLS — Excel 97-2003)

Arquivo no formato binário `.xls` (BIFF8), gerado pelo portal BR Premmia. Deve ser lido com a biblioteca **xlrd**.

A planilha relevante chama-se **"Conferência"**. O parser identifica as colunas pelo cabeçalho na primeira linha válida e filtra registros com `Status = "Processada"`.

Colunas esperadas: `CPF`, `Nome`, `Valor líquido`, `Data/Hora da transação`, `Código Transação`, `Forma de Pagamento`, `Status`.

| Forma de Pagamento (Premmia) | Categoria Final | Observação |
|---|---|---|
| PIX | `PREMMIA_PIX` (site) | Soma dos valores líquidos PIX Premmia |
| Cartão APP / Cartão | `PREMMIA_CARTAO` (site) | Soma dos valores líquidos cartão Premmia |
| Desconto / Cupom | `PREMMIA_CUPOM` (site) | Soma dos descontos/cupons Premmia |

### 3.4 FitCard — Valor Total

O total FitCard **não é importado automaticamente** — é digitado manualmente pelo usuário como campo numérico. O valor informado popula simultaneamente:

- `CARTAO_FITCARD` → coluna **site**
- `FITCARD` → coluna **sistema** (confirmação cruzada com o valor extraído do CAIXA CSV)

---

## 4. Telas e Módulos

### 4.1 Tela Principal — Histórico de Caixas

Tela inicial do aplicativo. Apresenta listagem paginada de todos os caixas registrados, ordenados por data decrescente.

**Componentes:**

- **Barra superior:** título "CaixaPos", versão, botão "Novo Caixa" (destaque primário).
- **Área de filtros:** campo de busca por data (aceita `DD/MM/AAAA` ou `AAAA-MM-DD`), dropdown de Status (`Todos / Rascunho / Conciliado`), botão Buscar.
- **Tabela de resultados:** colunas Data | Valor Sistema | Valor Site | Diferença Total | Status. Clique em qualquer linha abre o caixa.
- **Rodapé:** contagem de registros exibidos.

### 4.2 Tela de Caixa — Importação de Dados (Passo 1)

Criada ao clicar em "Novo Caixa" ou ao reabrir um rascunho. Organizada em seções empilhadas verticalmente com scroll.

#### Seção A — Data da Conciliação

- Campo de data com máscara `DD/MM/AAAA`, pré-preenchido com a data atual.

#### Seção B — Relatório do Sistema Interno (CAIXA CSV)

- Drop zone + botão "Selecionar Arquivo".
- Ao importar: exibe total de saídas extraídas, lista de itens detectados e chips agrupados por categoria.
- Botão "Remover" para trocar o arquivo.

#### Seção C — Relatório PagBank (CSV)

- Drop zone + botão "Selecionar Arquivo".
- Ao importar: exibe total de registros aprovados e chips com totais por categoria.
- Botão "Remover".

#### Seção D — FitCard

- Label: "Digite o valor total do FitCard (lado do site/adquirente)".
- Entry numérico com validação de float. Aceita vírgula ou ponto como separador decimal.
- Ícone ✓ verde ao digitar valor válido.

#### Seção E — Relatório Premmia (XLS)

- Drop zone + botão "Selecionar Arquivo".
- Ao importar: exibe total de transações processadas e chips com totais por forma de pagamento Premmia.
- Botão "Remover".

#### Rodapé da tela

- **"Salvar Rascunho"** — persiste o estado atual com `status="rascunho"`.
- **"Ver Resultado"** — navega para o Passo 2. Habilitado assim que o CSV do sistema interno for importado.

### 4.3 Tela de Conciliação — Resultado (Passo 2)

#### Tabela de Conciliação

Colunas: **Categoria | Sistema (R$) | Site (R$) | Diferença (R$) | Status**

- Diferença = Sistema − Site.
- Diferença = 0,00 → Status **"OK"** (verde).
- Diferença ≠ 0,00 → Status **"DIVERGENTE"** (vermelho). Valor da diferença em vermelho se negativo, laranja se positivo.
- Linhas com alternância de cor de fundo (zebra).

#### Categorias exibidas (ordem fixa)

| # | Categoria | Fonte dos valores |
|---|---|---|
| 1 | PREMMIA CARTÃO | Sistema: CAIXA CSV · Site: Premmia XLS |
| 2 | PREMMIA PIX | Sistema: CAIXA CSV · Site: Premmia XLS |
| 3 | PREMMIA CUPOM | Sistema: CAIXA CSV · Site: Premmia XLS |
| 4 | CARTÃO FITCARD | Sistema: zero · Site: campo manual FitCard |
| 5 | FITCARD | Sistema: CAIXA CSV · Site: zero |
| 6 | PAG PIX | Sistema: CAIXA CSV · Site: PagBank CSV |
| 7 | ELO CRÉDITO | Sistema: CAIXA CSV · Site: PagBank CSV |
| 8 | ELO DÉBITO | Sistema: CAIXA CSV · Site: PagBank CSV |
| 9 | MASTERCARD CRÉDITO | Sistema: CAIXA CSV · Site: PagBank CSV |
| 10 | MASTERCARD DÉBITO | Sistema: CAIXA CSV · Site: PagBank CSV |
| 11 | VISA CRÉDITO | Sistema: CAIXA CSV · Site: PagBank CSV |
| 12 | VISA DÉBITO | Sistema: CAIXA CSV · Site: PagBank CSV |

#### Informações adicionais (abaixo da tabela)

- Sangria: R$ valor (informativo)
- Notas a Prazo: R$ valor
- Despesas do Posto: R$ valor

#### Botões de ação

- **"Recomeçar"** — volta ao Passo 1 mantendo a data.
- **"Salvar Conciliação"** — altera status para `"conciliado"` e persiste no TinyDB.
- **"Exportar PDF"** — abre diálogo de salvar e gera o PDF.

### 4.4 Módulo — Contagem de Dinheiro

Acessível como aba lateral ou botão flutuante na tela de Caixa. Suporta **múltiplas contagens independentes** por caixa (ex.: cofre e caixinha separados).

#### Gerenciamento de contagens

- Botão "+ Nova Contagem" cria um painel com label editável ("Contagem 1", "Contagem 2", etc.).
- Contagens listadas em abas ou accordion. Cada aba pode ser excluída individualmente.

#### Interface de uma contagem

| Cédula | Valor Unit. | Qtde. (input) | Subtotal |
|---|---|---|---|
| R$ 200 | R$ 200,00 | `[ 0 ]` | R$ 0,00 |
| R$ 100 | R$ 100,00 | `[ 0 ]` | R$ 0,00 |
| R$ 50 | R$ 50,00 | `[ 0 ]` | R$ 0,00 |
| R$ 20 | R$ 20,00 | `[ 0 ]` | R$ 0,00 |
| R$ 10 | R$ 10,00 | `[ 0 ]` | R$ 0,00 |
| R$ 5 | R$ 5,00 | `[ 0 ]` | R$ 0,00 |
| R$ 2 | R$ 2,00 | `[ 0 ]` | R$ 0,00 |
| Moedas | — | `[ 0,00 ]` | R$ 0,00 |

- Total da contagem exibido em destaque abaixo do grid.
- Soma de todas as contagens exibida no rodapé do módulo.

#### Rastreio de notas de R$ 200

- Quando `qtde_200 > 0`, o sistema exibe automaticamente campos "Serial nota 1", "Serial nota 2", etc.
- Cada campo aceita **exatamente 5 caracteres numéricos** (últimos 5 dígitos do número de série).
- Validação em tempo real: campo vermelho se contiver letras ou comprimento ≠ 5.
- Seriais são **obrigatórios** para salvar a contagem quando `qtde_200 > 0`.

### 4.5 Exportação PDF

Gerado via **ReportLab**. O arquivo é salvo no caminho escolhido via `filedialog.asksaveasfilename`.

**Conteúdo do PDF:**

1. **Cabeçalho:** logotipo (se configurado), nome do estabelecimento, data do caixa, data/hora de exportação.
2. **Seção 1 — Resultado da Conciliação:** tabela com colunas Categoria / Sistema / Site / Diferença / Status.
3. **Seção 2 — Informações Complementares:** Sangria, Notas a Prazo, Despesas.
4. **Seção 3 — Contagem de Dinheiro:** para cada contagem, tabela com denominações, quantidades, subtotais e total. Notas de R$ 200 listadas com seus seriais.
5. **Rodapé de página:** número da página e nome do sistema.

---

## 5. Regras de Negócio

### 5.1 Importação e Parsing

- O CSV do sistema interno deve ser confirmado pelo conteúdo — procurar a string `"CAIXA GERAL"` nas primeiras 5 linhas.
- O CSV PagBank deve ser confirmado pelo cabeçalho contendo a coluna `"Código da Transação"`.
- O XLS Premmia deve ser detectado pelo **magic number OLE2** (primeiros bytes `D0 CF 11 E0`). Exibir erro amigável se o arquivo for enviado como CSV mas for binário.
- Valores monetários no CSV do sistema interno usam vírgula como decimal e ponto como milhar (ex.: `3.609,66`). O parser deve normalizar para `float` antes de somar.
- O mesmo arquivo não pode ser importado duas vezes na mesma seção sem remover o anterior.

### 5.2 Consolidação de Categorias

- `CARTAO_FITCARD` (site) recebe o valor do **campo manual FitCard**.
- `FITCARD` (sistema) recebe o valor `"CARTAO FITCARD"` extraído do CAIXA CSV.
- Ambos são categorias distintas na tabela — um representa o compromisso no sistema do posto, o outro o crédito na adquirente.
- `SANGRIA`, `NOTAS_A_PRAZO` e `DESPESAS_DO_POSTO` são campos **informativos**; não entram na tabela de conciliação.

### 5.3 Validações

- Data do caixa: obrigatória, não pode ser futura.
- Não é possível ter dois caixas com a mesma data. O sistema avisa e pergunta se o usuário quer sobrescrever.
- Campos numéricos aceitam vírgula ou ponto como decimal; qualquer outro caractere é rejeitado em tempo real.
- Seriais de R$ 200: exatamente 5 dígitos, somente números.

### 5.4 Status do Caixa

- **`rascunho`:** caixa salvo mas ainda não conciliado. Pode ser reaberto e editado livremente.
- **`conciliado`:** salvo via "Salvar Conciliação". Os campos de importação ficam bloqueados (somente leitura). Um botão **"Reabrir para edição"** recoloca o status em `rascunho`.

---

## 6. Layout e UX

### 6.1 Janela Principal

- Dimensão mínima: **900 × 650 px**. Redimensionável.
- Tema: ttkbootstrap tema padrão (`litera` ou `flatly`), sem customizações de cor além das indicadas neste documento.
- Navegação por telas via pilha interna (`Frame.pack / pack_forget`) ou `Notebook` com abas. Sem múltiplas janelas `Toplevel` (exceto diálogos modais).

### 6.2 Feedback ao Usuário

- Operações de leitura de arquivo rodam em **thread separada** com `Progressbar` indeterminate para não travar a GUI.
- Erros de parsing exibem `messagebox` com descrição legível (ex.: "O arquivo selecionado não é um CSV válido do sistema interno.").
- Ações destrutivas (excluir contagem, reabrir caixa conciliado) pedem confirmação via `messagebox.askyesno`.

### 6.3 Acessibilidade Básica

- Navegação completa por teclado (Tab / Shift+Tab entre campos).
- Labels descritivos em todos os campos de entrada.
- Contraste de cor compatível com WCAG AA (garantido pelo tema ttkbootstrap).

---

## 7. Arquitetura de Arquivos

```
caixapos/
├── main.py                 # entry point — inicia app tkinter
├── app.py                  # classe principal CaixaPosApp
├── db.py                   # wrapper TinyDB (CRUD de caixas)
├── parsers/
│   ├── __init__.py
│   ├── caixa_csv.py        # parser do relatório do sistema interno
│   ├── pagbank_csv.py      # parser do relatório PagBank
│   └── premmia_xls.py      # parser do relatório Premmia (.xls)
├── views/
│   ├── __init__.py
│   ├── historico.py        # tela de histórico de caixas
│   ├── importacao.py       # tela de importação (passo 1)
│   ├── resultado.py        # tela de resultado da conciliação (passo 2)
│   └── contagem.py         # módulo de contagem de dinheiro
├── export/
│   └── pdf_export.py       # geração do PDF com ReportLab
├── utils.py                # formatação de moeda, validações
├── assets/                 # ícones, logo
└── caixapos_db.json        # banco de dados TinyDB (gerado em runtime)
```

### 7.1 Build com PyInstaller

```bash
pyinstaller --onefile --windowed --name CaixaPos main.py
```

- Incluir `assets/` via `--add-data`.
- O banco `caixapos_db.json` deve residir no diretório de dados do usuário, não dentro do executável.
- O caminho do banco deve ser resolvido via `sys._MEIPASS` ou `appdirs.user_data_dir` para compatibilidade com o executável empacotado.

---

## 8. Critérios de Aceite

| # | Critério | Entrada | Resultado Esperado |
|---|---|---|---|
| CA-01 | Importar CAIXA CSV com itens POS e SMART para mesma bandeira | `1_CAIXA_16.csv` | `MASTERCARD_CREDITO` sistema = 1441,25 + 3609,66 = **5050,91** |
| CA-02 | Importar PagBank CSV e totalizar PIX | `2_Relatório...csv` | `PAG_PIX` site = soma de todos os Pix Aprovados |
| CA-03 | Importar XLS Premmia e categorizar por forma de pagamento | `3_premmia.xls` | `PREMMIA_CARTAO` site = soma de "Cartão APP" processados |
| CA-04 | Digitar FitCard popula CARTAO_FITCARD site e FITCARD sistema | Valor: 6646,12 | Ambas as categorias preenchidas com 6646,12 |
| CA-05 | Conciliação com diferença zero exibe status OK | Valores iguais em sistema e site | Status verde "OK" |
| CA-06 | Conciliação com divergência exibe valor em vermelho | Valores diferentes | Status vermelho "DIVERGENTE", diferença colorida |
| CA-07 | Nota de R$ 200 exige serial de 5 dígitos | Qtde. 200 = 2 | 2 campos de serial aparecem; bloqueia salvar se vazio |
| CA-08 | Exportar PDF gera arquivo legível | Caixa conciliado | PDF com tabela de conciliação e contagens de dinheiro |
| CA-09 | Duas datas iguais avisa o usuário | Data já existente no DB | Messagebox de confirmação antes de sobrescrever |
| CA-10 | Histórico filtra por data e status | Filtro combinado | Apenas caixas que atendem ambos os critérios aparecem |

---

## 9. Dependências Python

| Pacote | Versão Mín. | Uso |
|---|---|---|
| `ttkbootstrap` | 1.10 | Tema e widgets modernos para tkinter |
| `tinydb` | 4.8 | Banco de dados JSON local |
| `xlrd` | 2.0 | Leitura de arquivos `.xls` (Excel 97-2003) |
| `reportlab` | 4.0 | Geração de PDF |
| `tkcalendar` | 1.6 | Widget de seleção de data (opcional) |
| `pyinstaller` | 6.0 | Empacotamento do executável |

Todas as dependências devem ser listadas em `requirements.txt`. O CSV do sistema interno e o CSV PagBank são processados com o módulo `csv` da biblioteca padrão (sem dependência externa).

---

## Apêndice A — Glossário

| Termo | Definição |
|---|---|
| **Sistema** | Coluna da tabela de conciliação — valores registrados no PDV do posto |
| **Site** | Coluna da tabela de conciliação — valores registrados nas adquirentes/operadoras |
| **Sangria** | Retirada de numerário do caixa durante o dia; não entra na conciliação |
| **Adquirente** | Empresa que processa pagamentos com cartão (PagBank, Premmia, FitCard) |
| **POS** | Maquininha de cartão física (Point of Sale) |
| **SMART** | Terminal inteligente PagBank (variante de POS) |
| **FitCard** | Cartão de frota/benefício para frotas de veículos |
| **Premmia BR** | Programa de fidelidade da BR Distribuidora, aceito como forma de pagamento |
| **Serial R$ 200** | Últimos 5 dígitos do número de série impresso na cédula de R$ 200 (controle anti-fraude) |

---

## Apêndice B — Notas sobre o Arquivo Premmia

O arquivo Premmia exportado pelo portal é nominalmente salvo com extensão `.csv`, mas na realidade é um arquivo **Excel 97-2003 (`.xls`)** no formato BIFF8. Isso é detectável pelos primeiros bytes do arquivo:

```
D0 CF 11 E0 A1 B1 1A E1  ← magic number OLE2 Compound Document
```

O sistema deve **verificar o magic number em vez de confiar na extensão**. Lógica recomendada:

```python
def detectar_formato_premmia(caminho: str) -> str:
    with open(caminho, "rb") as f:
        magic = f.read(8)
    if magic == b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1":
        return "xls"   # usar xlrd
    return "csv"       # usar csv (stdlib)
```

Exibir um aviso informativo ao usuário indicando qual formato foi detectado e qual biblioteca foi usada para leitura.
