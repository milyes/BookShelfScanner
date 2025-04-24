import os
import logging
import tempfile
import cv2
import numpy as np
from pdf2image import convert_from_path

def enhance_pdf_image(image):
    """
    Améliore la qualité d'une image extraite d'un PDF pour une meilleure détection de texte.
    
    Args:
        image: L'image à améliorer (format ndarray de OpenCV).
        
    Returns:
        L'image améliorée.
    """
    try:
        # Convertir en niveaux de gris si l'image est en couleur
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Améliorer le contraste avec l'égalisation d'histogramme
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Appliquer une légère réduction de bruit
        denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)
        
        # Améliorer les bords
        edges = cv2.Canny(denoised, 50, 150)
        dilated = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
        
        # Combiner l'image originale avec les bords pour mettre en évidence le texte
        result = cv2.addWeighted(denoised, 0.8, dilated, 0.2, 0)
        
        # Reconvertir en BGR si l'image d'origine était en couleur
        if len(image.shape) == 3:
            result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
        
        return result
    except Exception as e:
        logging.error(f"Erreur lors de l'amélioration de l'image: {str(e)}")
        return image  # Retourner l'image originale en cas d'erreur

def process_pdf(pdf_path, output_pdf_path=None, enhance=True):
    """
    Traite un fichier PDF pour améliorer sa lisibilité et crée un nouveau PDF.
    
    Args:
        pdf_path: Chemin vers le fichier PDF d'entrée.
        output_pdf_path: Chemin pour le fichier PDF de sortie (optionnel).
        enhance: Si True, améliore la qualité des images extraites.
        
    Returns:
        Une liste des images améliorées.
    """
    from fpdf import FPDF
    
    if not os.path.exists(pdf_path):
        logging.error(f"Le fichier {pdf_path} est introuvable.")
        return None
    
    try:
        # Convertir le PDF en images
        logging.debug(f"Conversion du PDF {pdf_path} en images...")
        images = convert_from_path(pdf_path)
        
        enhanced_images = []
        
        if output_pdf_path:
            pdf = FPDF()
        
        for i, img in enumerate(images):
            # Convertir l'image PIL en format OpenCV
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            # Améliorer l'image si demandé
            if enhance:
                enhanced_img = enhance_pdf_image(img_cv)
            else:
                enhanced_img = img_cv
            
            enhanced_images.append(enhanced_img)
            
            # Si on doit créer un PDF de sortie
            if output_pdf_path:
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp:
                    temp_path = temp.name
                
                # Sauvegarder l'image améliorée
                cv2.imwrite(temp_path, enhanced_img)
                
                # Ajouter l'image au PDF
                pdf.add_page()
                pdf.image(temp_path, x=0, y=0, w=210, h=297)
                logging.debug(f"Page {i+1} ajoutée au PDF")
                
                # Supprimer le fichier temporaire
                os.remove(temp_path)
        
        # Sauvegarder le PDF si un chemin de sortie est fourni
        if output_pdf_path:
            pdf.output(output_pdf_path)
            logging.debug(f"Nouveau PDF généré : {output_pdf_path}")
        
        return enhanced_images
    
    except Exception as e:
        logging.error(f"Erreur lors du traitement du PDF: {str(e)}")
        return None