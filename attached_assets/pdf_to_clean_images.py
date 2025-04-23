# pdf_to_clean_images.py
import os
from pdf2image import convert_from_path
from fpdf import FPDF

INPUT_PDF = "Ouis_Tayeb_Fiche_Familiale.pdf"
OUTPUT_PDF = "Fiche_Familiale_Lisible_Images.pdf"
TEMP_IMG = "page_temp.jpg"

if not os.path.exists(INPUT_PDF):
    print(f"[!] Le fichier {INPUT_PDF} est introuvable.")
    exit(1)

print("[*] Conversion des pages PDF en images...")
try:
    images = convert_from_path(INPUT_PDF)
except Exception as e:
    print(f"[!] Erreur lors de la conversion : {e}")
    exit(1)

pdf = FPDF()
for i, img in enumerate(images):
    img.save(TEMP_IMG, "JPEG")
    pdf.add_page()
    pdf.image(TEMP_IMG, x=0, y=0, w=210, h=297)
    print(f"[+] Page {i+1} ajoutée")
    os.remove(TEMP_IMG)

pdf.output(OUTPUT_PDF)
print(f"[✓] Nouveau PDF généré : {OUTPUT_PDF}")

try:
    os.remove(INPUT_PDF)
    print(f"[-] Fichier original supprimé : {INPUT_PDF}")
except Exception as e:
    print(f"[!] Impossible de supprimer le fichier source : {e}")

CACHE_DIR = "/data/data/com.termux/files/usr/tmp" if "com.termux" in os.getcwd() else "/tmp"
print(f"[~] Nettoyage du cache temporaire ({CACHE_DIR})...")
for f in os.listdir(CACHE_DIR):
    fpath = os.path.join(CACHE_DIR, f)
    try:
        if os.path.isfile(fpath) and "poppler" in f:
            os.remove(fpath)
    except:
        pass

print("[✓] Nettoyage terminé.")
