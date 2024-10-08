from flask import Flask, request, jsonify
import numpy as np
import os
from io import BytesIO
from PIL import Image
import cv2
import onnxruntime as rt
import requests

app = Flask(__name__)

# Configuration dictionary with image size and class names
CONFIGURATION = {
    "IM_SIZE": 256,  # Ensure this matches the input size your model expects
    "CLASS_NAMES": ["ACCESSORIES", "BRACELETS", "CHAIN", "CHARMS", "EARRINGS",
                    "ENGAGEMENT RINGS", "ENGAGEMENT SET", "FASHION RINGS", "NECKLACES", "WEDDING BANDS"],
}

# Path to the ONNX model
MODEL_PATH = 'models/update_lenet_model_save_keras_quantized.onnx'

# Global ONNX Runtime session
onnx_session = None

def init_model():
    global onnx_session
    
    # Check if the model file exists locally
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model file not found at {MODEL_PATH}")
    
    # Load the ONNX model
    try:
        onnx_session = rt.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")

def preprocess_image(image):
    # Resize and preprocess the image for the model
    image = cv2.resize(image, (CONFIGURATION["IM_SIZE"], CONFIGURATION["IM_SIZE"]))
    image = image.astype(np.float32)  # Ensure numpy array is float32
    image = image / 255.0  # Normalize the image
    image = np.expand_dims(image, axis=0)  # Add batch dimension
    return image

@app.route('/predict', methods=['POST'])
def predict():
    if onnx_session is None:
        return jsonify({"error": "Model not loaded"}), 500

    try:
        # Parse the input data
        data = request.get_json()
        
        if 'image_url' in data:
            # Load image from the URL
            response = requests.get(data['image_url'])
            image = np.array(Image.open(BytesIO(response.content)).convert('RGB'))
        elif 'image_data' in data:
            # Load image from the provided image data
            image = np.array(data['image_data'], dtype=np.uint8)
        else:
            return jsonify({"error": "No valid input image provided."}), 400
        
        # Preprocess the image
        image = preprocess_image(image)
        
        # Get input and output names
        input_name = onnx_session.get_inputs()[0].name
        output_name = onnx_session.get_outputs()[0].name
        
        # Run the model to get predictions
        onnx_pred = onnx_session.run([output_name], {input_name: image})
        
        # Convert the output to a numpy array
        predictions = np.array(onnx_pred[0])
        
        # Get the top 3 predicted classes and their probabilities
        top_3_indices = np.argsort(predictions[0])[-3:][::-1]  # Top 3 indices
        top_3_probabilities = predictions[0][top_3_indices]
        top_3_classes = [CONFIGURATION['CLASS_NAMES'][index] for index in top_3_indices]
        
        # Prepare the results as a list of dictionaries
        top_3_classes_predictions = [
            {"class_name": top_3_classes[i], "probability": float(top_3_probabilities[i])}
            for i in range(3)
        ]
        
        # Return the JSON response with the top 3 predictions
        return jsonify({"top_3_classes_predictions": top_3_classes_predictions})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def hello():
    return "Hello! Welcome to the product type classification API with ONNX."

if __name__ == '__main__':
    init_model()  # Initialize the model before starting the server
    app.run(debug=False)
