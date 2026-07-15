import os
import asyncio
import base64
from playwright.async_api import async_playwright


async def download_manga_seguro(capitulo):
    output_dir = f"capitulos/capitulo_{capitulo}/imagens"
    os.makedirs(output_dir, exist_ok=True)

    async with async_playwright() as p:
        # headless=False ajuda a passar pelo Cloudflare sem problemas
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        target_url = f"https://readberserk.com/chapter/berserk-chapter-{capitulo}/"
        print(f"Acessando: {target_url}")
        await page.goto(target_url, wait_until="networkidle", timeout=0)

        img_locators = page.locator("img.pages__img")
        count = await img_locators.count()
        print(f"Total de imagens encontradas: {count}")

        for i in range(count):
            img_element = img_locators.nth(i)
            
            # Pega a URL real da imagem do atributo correto
            img_url = await img_element.get_attribute("data-src") or await img_element.get_attribute("src")
            
            if not img_url:
                continue

            file_name = f"page_{i+1:03d}.jpeg"
            file_path = os.path.join(output_dir, file_name)

            try:
                # JavaScript que faz o download usando o motor do próprio navegador carregado
                # Isso aproveita os cookies/tokens do Cloudflare sem violar as regras de CORS do canvas
                js_fetch_script = """
                async (url) => {
                    const response = await fetch(url);
                    const blob = await response.blob();
                    return new Promise((resolve) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result);
                        reader.readAsDataURL(blob);
                    });
                }
                """
                
                # Executa o fetch dentro do site e traz os dados em formato Base64 para o Python
                base64_data = await page.evaluate(js_fetch_script, img_url)

                if base64_data and "," in base64_data:
                    # Remove o cabeçalho do Base64 ("data:image/jpeg;base64,")
                    img_b64_clean = base64_data.split(",")[1]
                    img_bytes = base64.b64decode(img_b64_clean)
                    
                    with open(file_path, "wb") as f:
                        f.write(img_bytes)
                    print(f"Baixado via contexto da página: {file_name}")
                else:
                    print(f"Erro ao extrair dados da imagem {i+1}")
                    
            except Exception as e:
                print(f"Erro ao processar imagem {i+1}: {e}")

        await browser.close()

if __name__ == "__main__":
    capitulos_prequels = ["a0", "b0", "c0", "d0", "e0", "f0", "g0", "h0", "i0", "j0", "k0", "l0", "m0", "n0", "o0", "p0"]
    capitulos_extras = ["099-005", "364-5"]
    quantidade_de_capitulos = 386
    erros = []
    print("Baixando capítulos numerados...")
    for capitulo in range(1, quantidade_de_capitulos+1):
        capitulo_formatted = f"{capitulo:03d}"
        try:
            print(f"Baixando capítulo {capitulo_formatted}...")
            asyncio.run(download_manga_seguro(capitulo_formatted))
        except Exception as e:
            erros += [capitulo_formatted]
            print(f"Erro ao baixar capítulo {capitulo_formatted}: {e}")
    print("Capitulos numerados concluidos")

    print("Baixando capítulos prequels e extras...")
    for capitulo in capitulos_prequels + capitulos_extras:
        try:
            print(f"Baixando capítulo {capitulo}...")
            asyncio.run(download_manga_seguro(capitulo))
        except Exception as e:
            erros += [capitulo]
            print(f"Erro ao baixar capítulo {capitulo}: {e}")
    print("Capítulos prequels e extras concluídos")
    print("Download concluído")
    print(f"Capítulos com erro: {erros}")