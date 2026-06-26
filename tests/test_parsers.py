from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from parsers.caixa_csv import parse_caixa_csv
from parsers.pagbank_csv import parse_pagbank_csv


class ParserTests(unittest.TestCase):
    def test_caixa_sums_pos_and_smart(self):
        content = "\n".join(
            [
                "AUTO POSTO;17/06/2026;;;",
                "CAIXA GERAL;;;",
                "Empresa: 1;;;",
                "Periodo;;;",
                "Outro;;;",
                "FINANCEIRO;;;",
                "Entradas;Saidas;;",
                ";;POS PAGSEGURO MASTER.CRE;1.441,25",
                ";;SMART PAGSEGURO MASTER.C;3.609,66",
                ";;SANGRIA;9.176,00",
                "Subtotal;0;Subtotal;0",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "caixa.csv"
            path.write_text(content, encoding="latin-1")
            parsed = parse_caixa_csv(path)
        self.assertEqual(parsed["categorias"]["MASTERCARD_CREDITO"]["sistema"], 5050.91)
        self.assertEqual(parsed["sangria"], 9176.0)

    def test_pagbank_filters_approved_and_groups_pix(self):
        content = "\n".join(
            [
                "Documento;Código da Transação;Bandeira;Forma de Pagamento;Valor Bruto;Status",
                ";1;;Pix;10,00;Aprovada",
                ";2;;Pix;5,50;Cancelada",
                ";3;Visa;Débito;20,00;Aprovada",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pagbank.csv"
            path.write_text(content, encoding="utf-8-sig")
            parsed = parse_pagbank_csv(path)
        self.assertEqual(parsed["categorias"]["PAG_PIX"]["site"], 10.0)
        self.assertEqual(parsed["categorias"]["VISA_DEBITO"]["site"], 20.0)
        self.assertEqual(parsed["registros_aprovados"], 2)


if __name__ == "__main__":
    unittest.main()
