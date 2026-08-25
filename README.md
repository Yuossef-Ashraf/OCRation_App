# OCRation - Document OCR and Translation App

A document text recognition (OCR) and LLM-powered translation application with Flask Web and PyQt desktop interfaces.

## Project Structure
- **Code**: `run_web.py, ocration_qt.py, image_ocr.py, llm_model.py`
- **Dataset / Resources**: `architecture_flowchart.png, document test samples`
- **Documentation**: `README.md`

## Architecture
![System Architecture](architecture_flowchart.png)

## Requirements
```bash
pip install flask requests numpy opencv-python groq python-dotenv pyqt5
```

## Usage
1. Clone the repository:
```bash
git clone https://github.com/Yuossef-Ashraf/OCRation_App.git
cd OCRation_App
```
2. Run the project:
```bash
jupyter notebook "run_web.py, ocration_qt.py, image_ocr.py, llm_model.py"
```

## Author
Yuossef Ashraf

## License
MIT License
