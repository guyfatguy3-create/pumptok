from http.server import BaseHTTPRequestHandler
from PIL import Image
import numpy as np
from io import BytesIO
import base64
import json
import os
import cgi

def process_image(image_data):
    """Apply green/white pumpify effect and add pill overlay"""
    
    # Open image
    img = Image.open(BytesIO(image_data)).convert('RGBA')
    
    # Convert to numpy array
    arr = np.array(img)
    
    # Extract RGB channels
    r = arr[:, :, 0].astype(float)
    g = arr[:, :, 1].astype(float)
    b = arr[:, :, 2].astype(float)
    a = arr[:, :, 3]
    
    # Calculate luminance
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    
    # Create green/white effect
    # Bright areas -> white with green tint
    # Dark areas -> green tones
    
    new_r = np.where(lum > 180, np.clip(lum * 0.95, 0, 255), np.clip(lum * 0.5, 0, 255))
    new_g = np.where(lum > 180, np.clip(lum, 0, 255), np.clip(lum * 0.9 + 80, 0, 255))
    new_b = np.where(lum > 180, np.clip(lum * 0.95, 0, 255), np.clip(lum * 0.5, 0, 255))
    
    # Reconstruct image
    result = np.stack([
        new_r.astype(np.uint8),
        new_g.astype(np.uint8),
        new_b.astype(np.uint8),
        a
    ], axis=-1)
    
    result_img = Image.fromarray(result, 'RGBA')
    
    # Load and add pill overlay
    try:
        pill_path = os.path.join(os.path.dirname(__file__), '..', 'pill.png')
        if os.path.exists(pill_path):
            pill = Image.open(pill_path).convert('RGBA')
            
            # Calculate pill size (25% of smaller dimension)
            pill_size = int(min(result_img.width, result_img.height) * 0.25)
            pill = pill.resize((pill_size, pill_size), Image.Resampling.LANCZOS)
            
            # Position in bottom right corner
            pill_x = result_img.width - pill_size - 20
            pill_y = result_img.height - pill_size - 20
            
            # Create a new image for compositing
            result_img.paste(pill, (pill_x, pill_y), pill)
    except Exception as e:
        print(f"Pill overlay error: {e}")
    
    # Convert to bytes
    output = BytesIO()
    result_img.save(output, format='PNG')
    output.seek(0)
    
    return output.getvalue()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            
            if 'multipart/form-data' in content_type:
                # Parse boundary
                boundary = content_type.split('boundary=')[1]
                
                # Read body
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                
                # Simple multipart parser
                parts = body.split(f'--{boundary}'.encode())
                
                image_data = None
                for part in parts:
                    if b'Content-Type: image' in part:
                        # Find the start of image data (after double CRLF)
                        header_end = part.find(b'\r\n\r\n')
                        if header_end != -1:
                            image_data = part[header_end + 4:]
                            # Remove trailing boundary markers
                            if image_data.endswith(b'\r\n'):
                                image_data = image_data[:-2]
                            if image_data.endswith(b'--'):
                                image_data = image_data[:-2]
                            if image_data.endswith(b'\r\n'):
                                image_data = image_data[:-2]
                            break
                
                if image_data:
                    # Process the image
                    result = process_image(image_data)
                    
                    # Return the processed image
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', len(result))
                    self.end_headers()
                    self.wfile.write(result)
                else:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'No image found in request'}).encode())
            else:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Invalid content type'}).encode())
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
