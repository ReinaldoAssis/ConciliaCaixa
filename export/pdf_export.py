from __future__ import annotations

from datetime import datetime
from pathlib import Path

from constants import DENOMINATIONS, build_conciliation_rows
from utils import date_to_br, format_money


def export_caixa_pdf(caixa: dict, output_path: str | Path) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("Instale reportlab para exportar PDF.") from exc

    path = Path(output_path)
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("CaixaPos - Auto Posto Lagoa Cafe", styles["Title"]),
        Paragraph(f"Data do caixa: {date_to_br(caixa['data'])}", styles["Normal"]),
        Paragraph(f"Exportado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]),
        Spacer(1, 0.4 * cm),
        Paragraph("Resultado da Conciliacao", styles["Heading2"]),
    ]

    table_data = [["Categoria", "Sistema", "Site", "Diferenca", "Status"]]
    for row in build_conciliation_rows(caixa.get("categorias", {})):
        table_data.append(
            [
                row["label"],
                format_money(row["sistema"]),
                format_money(row["site"]),
                format_money(row["diferenca"]),
                row["status"],
            ]
        )
    table = Table(table_data, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#adb5bd")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (-1, 1), (-1, -1), "CENTER"),
            ]
        )
    )
    story.extend([table, Spacer(1, 0.4 * cm), Paragraph("Informacoes Complementares", styles["Heading2"])])
    story.append(
        Table(
            [
                ["Sangria", format_money(caixa.get("sangria", 0))],
                ["Notas a Prazo", format_money(caixa.get("notas_a_prazo", 0))],
                ["Despesas do Posto", format_money(caixa.get("despesas", 0))],
            ],
            hAlign="LEFT",
        )
    )

    story.extend([Spacer(1, 0.4 * cm), Paragraph("Contagem de Dinheiro", styles["Heading2"])])
    contagens = caixa.get("contagens_dinheiro") or []
    if not contagens:
        story.append(Paragraph("Nenhuma contagem registrada.", styles["Normal"]))
    for contagem in contagens:
        story.append(Paragraph(contagem.get("label", "Contagem"), styles["Heading3"]))
        rows = [["Cedula", "Quantidade", "Subtotal"]]
        notas = contagem.get("notas", {})
        for denom in DENOMINATIONS:
            qty = int(notas.get(str(denom), 0) or 0)
            rows.append([f"R$ {denom}", str(qty), format_money(qty * denom)])
        rows.append(["Moedas", "", format_money(contagem.get("moedas", 0))])
        rows.append(["Total", "", format_money(contagem.get("total", 0))])
        story.append(Table(rows, hAlign="LEFT"))
        serials = contagem.get("seriais_200") or []
        if serials:
            story.append(Paragraph("Seriais R$ 200: " + ", ".join(serials), styles["Normal"]))
        story.append(Spacer(1, 0.2 * cm))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(1.5 * cm, 1 * cm, "CaixaPos")
        canvas.drawRightString(19.5 * cm, 1 * cm, f"Pagina {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path
