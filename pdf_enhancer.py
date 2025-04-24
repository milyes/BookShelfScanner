import os
import logging
import tempfile
import cv2
import numpy as np
from pdf2image import convert_from_path
from fpdf import FPDF
import shutil
from datetime import datetime

# Configurer le logging
logging.basicConfig(level=logging.DEBUG)

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

def clean_pdf_convert_to_images(pdf_path, temp_dir=None, delete_original=False):
    """
    Convertit un PDF en images améliorées et nettoie le cache Poppler.
    Basé sur le script pdf_to_clean_images.py.
    
    Args:
        pdf_path: Chemin vers le fichier PDF d'entrée.
        temp_dir: Dossier pour les fichiers temporaires (optionnel).
        delete_original: Si True, supprime le fichier PDF original après traitement.
        
    Returns:
        Une liste des chemins d'images générées.
    """
    if not os.path.exists(pdf_path):
        logging.error(f"[!] Le fichier {pdf_path} est introuvable.")
        return []
    
    # Créer un dossier temporaire si nécessaire
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()
    
    image_paths = []
    
    try:
        # Conversion du PDF en images
        logging.debug(f"[*] Conversion des pages PDF en images...")
        images = convert_from_path(pdf_path)
        
        for i, img in enumerate(images):
            # Sauvegarder l'image
            img_path = os.path.join(temp_dir, f"page_{i+1}.jpg")
            img.save(img_path, "JPEG")
            image_paths.append(img_path)
            logging.debug(f"[+] Page {i+1} sauvegardée: {img_path}")
        
        # Suppression du fichier original si demandé
        if delete_original:
            try:
                os.remove(pdf_path)
                logging.debug(f"[-] Fichier original supprimé : {pdf_path}")
            except Exception as e:
                logging.error(f"[!] Impossible de supprimer le fichier source : {e}")
        
        # Nettoyage du cache Poppler
        try:
            cache_dir = "/tmp"
            logging.debug(f"[~] Nettoyage du cache temporaire ({cache_dir})...")
            for f in os.listdir(cache_dir):
                fpath = os.path.join(cache_dir, f)
                if os.path.isfile(fpath) and "poppler" in f:
                    os.remove(fpath)
            logging.debug("[✓] Nettoyage terminé.")
        except Exception as e:
            logging.warning(f"[!] Erreur lors du nettoyage du cache : {e}")
            
        return image_paths
    
    except Exception as e:
        logging.error(f"[!] Erreur lors de la conversion : {e}")
        return []

def restore_image(image_path, output_path=None):
    """
    Restaure une image endommagée ou dégradée en utilisant des techniques de traitement d'image avancées.
    
    Args:
        image_path: Chemin vers l'image à restaurer.
        output_path: Chemin pour sauvegarder l'image restaurée (optionnel).
        
    Returns:
        L'image restaurée au format OpenCV (ndarray) ou le chemin de sortie si spécifié.
    """
    if not os.path.exists(image_path):
        logging.error(f"L'image {image_path} est introuvable.")
        return None
    
    try:
        # Charger l'image
        image = cv2.imread(image_path)
        if image is None:
            logging.error(f"Impossible de lire l'image: {image_path}")
            return None
        
        # Créer une copie de l'image originale pour comparaison
        original = image.copy()
        
        # Convertir en niveaux de gris
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        
        # 1. Correction de la luminosité et du contraste
        alpha = 1.3  # Contraste (1.0-3.0)
        beta = 10    # Luminosité (0-100)
        adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
        
        # 2. Réduction du bruit
        denoised = cv2.fastNlMeansDenoising(adjusted, None, 10, 7, 21)
        
        # 3. Amélioration des bords
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        
        # 4. Correction automatique des couleurs si l'image est en couleur
        if len(original.shape) == 3:
            # Appliquer la correction des contrastes sur chaque canal
            restored_color = np.zeros_like(original)
            for i in range(3):  # Pour chaque canal RGB
                channel = original[:,:,i]
                # Égalisation adaptative de l'histogramme
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                restored_channel = clahe.apply(channel)
                restored_color[:,:,i] = restored_channel
            
            # Fusionner avec l'image améliorée en niveaux de gris
            restored = cv2.addWeighted(restored_color, 0.7, cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR), 0.3, 0)
        else:
            restored = sharpened
        
        # Sauvegarder l'image restaurée si un chemin est fourni
        if output_path:
            cv2.imwrite(output_path, restored)
            logging.debug(f"Image restaurée sauvegardée: {output_path}")
            return output_path
        
        return restored
    
    except Exception as e:
        logging.error(f"Erreur lors de la restauration de l'image: {str(e)}")
        return None

def restore_document(doc_path, output_path=None):
    """
    Restaure un document (PDF) endommagé ou dégradé.
    Traite chaque page individuellement pour une meilleure restauration.
    
    Args:
        doc_path: Chemin vers le document à restaurer.
        output_path: Chemin pour le document restauré (optionnel).
        
    Returns:
        Le chemin du document restauré si output_path est spécifié, sinon None.
    """
    if not os.path.exists(doc_path):
        logging.error(f"Le document {doc_path} est introuvable.")
        return None
    
    # Vérifier l'extension du fichier
    file_ext = os.path.splitext(doc_path)[1].lower()
    if file_ext != '.pdf':
        logging.error(f"Format de document non pris en charge: {file_ext}. Seuls les PDF sont supportés.")
        return None
    
    # Créer un dossier temporaire pour les images extraites
    temp_dir = tempfile.mkdtemp()
    temp_restored_dir = tempfile.mkdtemp()
    
    try:
        # 1. Extraire les pages du PDF
        logging.debug(f"Extraction des pages du document {doc_path}...")
        images = convert_from_path(doc_path)
        
        # Définir le chemin de sortie si non spécifié
        if output_path is None:
            file_name = os.path.basename(doc_path)
            base_name = os.path.splitext(file_name)[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(os.path.dirname(doc_path), f"{base_name}_restored_{timestamp}.pdf")
        
        # 2. Créer un nouveau PDF pour le document restauré
        pdf = FPDF()
        
        # 3. Traiter chaque page
        for i, img in enumerate(images):
            # Sauvegarder l'image temporairement
            temp_img_path = os.path.join(temp_dir, f"page_{i+1}.jpg")
            img.save(temp_img_path, "JPEG")
            
            # Restaurer l'image
            restored_img_path = os.path.join(temp_restored_dir, f"restored_page_{i+1}.jpg")
            restored = restore_image(temp_img_path, restored_img_path)
            
            if restored is not None:
                # Ajouter la page restaurée au PDF
                pdf.add_page()
                pdf.image(restored_img_path, x=0, y=0, w=210, h=297)  # Format A4
                logging.debug(f"Page {i+1} restaurée et ajoutée au PDF")
        
        # 4. Sauvegarder le PDF restauré
        pdf.output(output_path)
        logging.debug(f"Document restauré sauvegardé: {output_path}")
        
        # 5. Nettoyer les fichiers temporaires
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(temp_restored_dir, ignore_errors=True)
        
        return output_path
    
    except Exception as e:
        logging.error(f"Erreur lors de la restauration du document: {str(e)}")
        # Nettoyer en cas d'erreur
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(temp_restored_dir, ignore_errors=True)
        return None

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
    if not os.path.exists(pdf_path):
        logging.error(f"Le fichier {pdf_path} est introuvable.")
        return None
    
    try:
        # Convertir le PDF en images
        logging.debug(f"Conversion du PDF {pdf_path} en images...")
        images = convert_from_path(pdf_path)
        
        enhanced_images = []
        
        # Créer un nouveau PDF si un chemin de sortie est fourni
        pdf = None
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
        if output_pdf_path and pdf is not None:
            pdf.output(output_pdf_path)
            logging.debug(f"Nouveau PDF généré : {output_pdf_path}")
        
        return enhanced_images
    
    except Exception as e:
        logging.error(f"Erreur lors du traitement du PDF: {str(e)}")
        return None