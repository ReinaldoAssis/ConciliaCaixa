# CaixaPos

Aplicacao desktop para fechamento e conciliacao de caixa de posto de combustivel.

## Instalar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Rodar

```bash
python main.py
```

O banco local `caixapos_db.json` e criado no diretorio de dados do usuario. Para testes locais, defina `CAIXAPOS_DATA_DIR` apontando para uma pasta temporaria.

## Testes

```bash
python -m unittest discover
```

## Build

```bash
pyinstaller --onefile --windowed --name CaixaPos main.py
```
