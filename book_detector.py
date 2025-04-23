import cv2
import numpy as np
import pytesseract
import logging
import re

def detect_books(image):
    """
    Detect books in the given image and return a list of cropped book images.
    
    Args:
        image: The input image containing bookshelves.
        
    Returns:
        List of cropped book images.
    """
    logging.debug("Starting book detection...")
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Apply edge detection
    edges = cv2.Canny(blurred, 50, 150)
    
    # Dilate the edges to connect them
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter contours to find potential books
    book_images = []
    for contour in contours:
        # Calculate contour area and discard small contours
        area = cv2.contourArea(contour)
        if area < 1000:  # Adjust this threshold based on your images
            continue
        
        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter out contours that are too small to be books
        if w < 30 or h < 100:
            continue
        
        # Aspect ratio filtering - books are usually taller than wide
        aspect_ratio = h / float(w)
        if 0.5 <= aspect_ratio <= 10:  # Adjust these thresholds as needed
            # Crop the book from the original image
            book_image = image[y:y+h, x:x+w]
            book_images.append(book_image)
    
    logging.debug(f"Detected {len(book_images)} potential books")
    
    # If we didn't find any books using contour approach, try simple division
    if len(book_images) == 0:
        logging.debug("Using fallback method for book detection")
        book_images = detect_books_by_division(image)
    
    return book_images

def detect_books_by_division(image):
    """
    Fallback method to detect books by dividing the image.
    
    Args:
        image: The input image containing bookshelves.
        
    Returns:
        List of cropped book images.
    """
    height, width = image.shape[:2]
    
    # Estimate typical book width (assume books take around 1/8 of the image width)
    est_book_width = width // 8
    
    # Divide the image into potential book regions
    book_images = []
    for x in range(0, width, est_book_width):
        if x + est_book_width <= width:
            book_image = image[:, x:x+est_book_width]
            book_images.append(book_image)
    
    return book_images

def extract_book_info(book_image):
    """
    Extract book information from a book image using OCR.
    
    Args:
        book_image: The image of a single book.
        
    Returns:
        A dictionary containing book information.
    """
    logging.debug("Extracting book information...")
    
    # Enhance image for better OCR
    # Convert to grayscale
    gray = cv2.cvtColor(book_image, cv2.COLOR_BGR2GRAY)
    
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY, 11, 2)
    
    # Perform OCR on the enhanced image
    try:
        text = pytesseract.image_to_string(thresh)
    except Exception as e:
        logging.error(f"OCR error: {str(e)}")
        text = ""
    
    # Clean up the text
    text = text.strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Extract book information
    book_info = {
        'title': 'Unknown Title',
        'author': 'Unknown Author',
        'publisher': 'Unknown Publisher',
        'isbn': 'N/A',
        'raw_text': text,
        'confidence': 'Low'
    }
    
    # If we have extracted text
    if lines:
        # Analyze the extracted text to determine book details
        
        # Title is usually the largest text on the spine, often the first line
        if len(lines) > 0:
            book_info['title'] = lines[0]
            
        # Author is often the second line
        if len(lines) > 1:
            book_info['author'] = lines[1]
        
        # Look for ISBN pattern
        isbn_pattern = r'(?:ISBN(?:-1[03])?:? )?(?=[0-9X]{10}|(?=(?:[0-9]+[- ]){3})[- 0-9X]{13}|97[89][0-9]{10}|(?=(?:[0-9]+[- ]){4})[- 0-9]{17})(?:97[89][- ]?)?[0-9]{1,5}[- ]?[0-9]+[- ]?[0-9]+[- ]?[0-9X]'
        isbn_match = re.search(isbn_pattern, text)
        if isbn_match:
            book_info['isbn'] = isbn_match.group(0)
            book_info['confidence'] = 'High'
        
        # Assign confidence based on amount of text extracted
        if len(text) > 50:
            book_info['confidence'] = 'Medium'
        if len(text) > 100:
            book_info['confidence'] = 'High'
    
    return book_info
