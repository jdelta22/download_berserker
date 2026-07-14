from pathlib import Path
import img2pdf

# Pasta que contém todos os capítulos
PASTA_CAPITULOS = Path("capitulos")

# Percorre cada capítulo
for capitulo in PASTA_CAPITULOS.iterdir():

    # Ignora arquivos
    if not capitulo.is_dir():
        continue

    pasta_imagens = capitulo / "imagens"

    # Ignora se não existir a pasta imagens
    if not pasta_imagens.is_dir():
        print(f"{capitulo.name}: pasta 'imagens' não encontrada.")
        continue

    # Busca todas as imagens page_*.jpeg
    imagens = sorted(pasta_imagens.glob("page_*.jpeg"))

    if not imagens:
        print(f"{capitulo.name}: nenhuma imagem encontrada.")
        continue

    # Caminho do PDF
    pdf_saida = capitulo / f"{capitulo.name}.pdf"

    # Cria o PDF
    with open(pdf_saida, "wb") as pdf:
        pdf.write(img2pdf.convert([str(img) for img in imagens]))

    print(f"✓ Criado: {pdf_saida}")