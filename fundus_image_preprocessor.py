import os
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt

def create_directory(directory_path):
    """Crear directorio si no existe"""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

def preserve_color_enhancement(image):
    """Mejorar el contraste preservando los colores originales"""
    # Convertir a LAB para separar la luminosidad del color
    lab = cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    # Aplicar CLAHE solo al canal de luminancia con parámetros más suaves
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    
    # Fusionar de nuevo con los canales de color originales
    enhanced_lab = cv2.merge([cl, a, b])
    enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    
    return enhanced_bgr

def remove_background_bgr(image):
    """Remover el fondo negro de la imagen manteniendo el formato BGR"""
    # Convertir a escala de grises
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Aplicar umbral para separar el objeto de interés del fondo
    _, thresh = cv2.threshold(gray, 20, 255, cv2.THRESH_BINARY)
    
    # Mejorar la máscara con operaciones morfológicas
    kernel = np.ones((3,3), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
    
    # Crear una máscara
    mask = np.zeros(image.shape[:2], np.uint8)
    
    # Encontrar contornos
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Dibujar solo el contorno más grande
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) > 100:
            cv2.drawContours(mask, [largest_contour], -1, (255), -1)
    
    # Aplicar la máscara para crear una imagen con fondo transparente
    bgra = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = mask
    
    return bgra

def verify_transparency(image_path):
    """Verificar que la imagen procesada no tiene artefactos"""
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return False
    
    # Verificar si hay píxeles blancos aislados en la esquina superior izquierda
    height, width = img.shape[:2]
    check_h = min(50, height)
    check_w = min(50, width)
    
    top_left = img[0:check_h, 0:check_w]
    if len(img.shape) == 4:  # Si tiene canal alfa
        # Buscar píxeles blancos con alfa completo
        white_pixels = np.all(top_left[:,:,:3] > 240, axis=2) & (top_left[:,:,3] > 240)
        if np.any(white_pixels):
            # Hacer transparentes estos píxeles
            for i in range(check_h):
                for j in range(check_w):
                    if white_pixels[i, j]:
                        img[i, j] = [0, 0, 0, 0]
            cv2.imwrite(image_path, img)
            return True
    return False

def process_fundus_image(image_path, output_dir):
    """Procesar una imagen de fondo de ojo y guardar resultados"""
    try:
        # Leer imagen en BGR (formato nativo de OpenCV)
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: No se pudo cargar la imagen {image_path}")
            return None
        
        # Aplicar mejora de contraste preservando colores
        enhanced = preserve_color_enhancement(image)
        
        # Remover fondo (trabajar con BGR en lugar de RGB)
        enhanced_no_bg = remove_background_bgr(enhanced)
        
        # Obtener nombre de archivo original
        filename = os.path.basename(image_path)
        base_name, ext = os.path.splitext(filename)
        
        # Guardar imagen mejorada con fondo transparente
        output_path = os.path.join(output_dir, base_name + ".png")
        # Guardar directamente en BGRA para PNG
        cv2.imwrite(output_path, enhanced_no_bg)
        
        # Verificar y corregir posibles artefactos
        verify_transparency(output_path)
        
        return {
            "image_path": image_path,
            "output_path": output_path,
            "status": "success"
        }
    except Exception as e:
        print(f"Error procesando {image_path}: {str(e)}")
        return {
            "image_path": image_path,
            "status": "error",
            "error": str(e)
        }

def batch_process_images(base_dir, output_base_dir):
    """Procesar todas las imágenes en la estructura de directorios dada"""
    # Crear directorio de salida
    create_directory(output_base_dir)
    results = []

    subsets = ["TRAIN", "TEST", "VAL"]
    classes = ["0", "1"]

    for subset in subsets:
        subset_dir = os.path.join(base_dir, subset)
        subset_output_dir = os.path.join(output_base_dir, subset)
        create_directory(subset_output_dir)

        for cls in classes:
            class_dir = os.path.join(subset_dir, cls)
            class_output_dir = os.path.join(subset_output_dir, cls)
            create_directory(class_output_dir)

            if os.path.exists(class_dir):
                for img_name in tqdm(os.listdir(class_dir), desc=f"Procesando {subset}/{cls}"):
                    if img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                        img_path = os.path.join(class_dir, img_name)
                        result = process_fundus_image(img_path, class_output_dir)
                        if result:
                            results.append(result)

    # Guardar resultados en CSV
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(output_base_dir, "preprocessing_results.csv"), index=False)

    print(f"Procesamiento completado. Resultados guardados en {output_base_dir}")
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    print(f"Total de imágenes procesadas: {len(results)}")
    print(f"Exitosas: {success_count}")
    print(f"Con errores: {error_count}")

if __name__ == "__main__":
    # Directorio base donde se encuentran las carpetas TRAIN y TEST
    # Por ejemplo:
    # base_dir = r"C:\Documents\DISAESE\DIABETIC-RETINOPATHY\DEEPDRID-DIABETIC-RETINOPATHY"
    base_dir = r""
    
    # Directorio donde se guardarán los resultados del preprocesamiento
    # Por ejemplo:
    # output_base_dir = r"C:\Documents\DISAESE\DIABETIC-RETINOPATHY\DEEPDRID-DIABETIC-RETINOPATHY_PREPROCESSED"
    output_base_dir = r""
    
    # Ejecutar el procesamiento por lotes
    batch_process_images(base_dir, output_base_dir)