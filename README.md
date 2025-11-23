# OCRation App 📄🔍

An AI-powered Document Optical Character Recognition (OCR) and Translation application. **OCRation** allows users to extract text from images and documents with high precision and process or translate the content using Groq LLMs and the OCR.Space engine.

Features both a **Flask Web Interface** and a **PyQt Desktop GUI**.

## Features ✨
- **High-Accuracy OCR**: Extract text from images (JPG, PNG, WebP) and documents using OCR.Space Engine.
- **LLM Text Processing**: AI-powered text translation, summarization, and formatting powered by Groq API.
- **Dual Interface**:
  - **Web Application**: Responsive web app powered by Flask.
  - **Desktop Application**: Desktop GUI built with PyQt.
- **Automatic Image Optimization**: Pre-processes and resizes large images for optimal OCR performance.
- **Security & Logging**: Integrated rate limiting, input validation, and security logging.

## Tech Stack 🛠️
- **Backend & Logic**: Python 3.10+, Flask, PyQt
- **Computer Vision**: OpenCV (`cv2`), NumPy
- **AI / Cloud Services**: Groq API, OCR.Space API
- **Utilities**: Python-Dotenv, Requests

## Project Structure 📂
```
OCRation_App/
├── web/                   # Flask Web Application
│   ├── app.py             # Web server entry point
│   ├── security.py        # Security & input validation
│   └── templates/         # HTML templates
├── image_ocr.py           # Core OCR extraction engine
├── llm_model.py           # Groq LLM integration
├── ocration_qt.py         # PyQt Desktop GUI
├── run_web.py             # Web App launcher
├── logging_config.py      # Logger configuration
├── fix_mobile_access.ps1  # Windows firewall helper script
└── start_app.bat          # Startup script
```

## Setup & Installation 🚀

### 1. Clone the repository
```bash
git clone https://github.com/Yuossef-Ashraf/OCRATION.git
cd OCRATION
```

### 2. Set up virtual environment
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install flask requests numpy opencv-python groq python-dotenv deep-translator pyqt5
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```
Edit `.env`:
```env
GROQ_API_KEY=gsk_your_groq_api_key
OCR_SPACE_API_KEY=your_ocr_space_key
```

## Running the Application 💻

### Launch Web Server
```bash
python run_web.py
```
Open your browser at `http://127.0.0.1:5000`.

### Launch Desktop GUI
```bash
python ocration_qt.py
```

## Author 👤
Created and maintained by **Yuossef Ashraf**.

## License 📜
Distributed under the MIT License.
