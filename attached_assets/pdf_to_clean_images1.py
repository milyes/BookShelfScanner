import fitz  # PyMuPDF
import os

def extract_images_from_pdf(pdf_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    doc = fitz.open(pdf_path)
    image_count = 0

    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)
        for img_index, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image_filename = f"image_{page_index+1}_{img_index+1}.{image_ext}"
            with open(os.path.join(output_folder, image_filename), "wb") as img_file:
                img_file.write(image_bytes)
            image_count += 1

    print(f"{image_count} images extraites depuis {pdf_path}.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python pdf_to_clean_images1.py <pdf_path> <output_folder>")
    else:
        extract_images_from_pdf(sys.argv[1], sys.argv[2])

