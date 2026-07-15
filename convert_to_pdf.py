from pathlib import Path
import img2pdf
from PIL import Image

PASTA_CAPITULOS = Path("capitulos")
DPI_PADRAO = 96  # força DPI fixo, ignorando metadado (possivelmente errado) do JPEG

def imagem_valida(caminho, tamanho_minimo_px=10):
    """Verifica se a imagem abre e tem dimensões razoáveis."""
    try:
        with Image.open(caminho) as img:
            img.verify()  # detecta corrupção
        with Image.open(caminho) as img:  # reabre pois verify() invalida o objeto
            w, h = img.size
            if w < tamanho_minimo_px or h < tamanho_minimo_px:
                return False, f"dimensões muito pequenas ({w}x{h})"
        return True, None
    except Exception as e:
        return False, f"corrompida ou ilegível ({e})"

for capitulo in PASTA_CAPITULOS.iterdir():
    if not capitulo.is_dir():
        continue

    pasta_imagens = capitulo / "imagens"
    if not pasta_imagens.is_dir():
        print(f"{capitulo.name}: pasta 'imagens' não encontrada.")
        continue

    imagens = sorted(pasta_imagens.glob("page_*.jpeg"))
    if not imagens:
        print(f"{capitulo.name}: nenhuma imagem encontrada.")
        continue

    imagens_ok = []
    for img in imagens:
        ok, motivo = imagem_valida(img)
        if ok:
            imagens_ok.append(img)
        else:
            print(f"  ⚠ {capitulo.name}: ignorando {img.name} — {motivo}")

    if not imagens_ok:
        print(f"{capitulo.name}: nenhuma imagem válida após checagem.")
        continue

    pdf_saida = capitulo / f"{capitulo.name}.pdf"

    try:
        layout_fun = img2pdf.get_layout_fun(None, None, None, None, DPI_PADRAO)
        with open(pdf_saida, "wb") as pdf:
            pdf.write(img2pdf.convert(
                [str(img) for img in imagens_ok],
                dpi=DPI_PADRAO,
                layout_fun=layout_fun,
            ))
        print(f"✓ Criado: {pdf_saida} ({len(imagens_ok)}/{len(imagens)} páginas)")
    except Exception as e:
        print(f"✗ Falhou {capitulo.name}: {e}")
        continue