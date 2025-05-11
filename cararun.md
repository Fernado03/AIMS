## Backend Setup and Run Instructions

These instructions will guide you through setting up and running the Python Flask backend for the AI Medical Scribe application.

### Prerequisites
- Python 3.x installed.
- `pip` (Python package installer) installed.
- Access to a terminal or command prompt.
- Your Google Cloud service account JSON key file (e.g., `macro-dolphin-432908-t4-1257da99b275.json`) downloaded and placed in the project root directory.

### 1. Set up a Python Virtual Environment
It's highly recommended to use a virtual environment to manage project dependencies.

Navigate to the project root directory in your terminal:
```bash
cd path/to/AIMS-website
```

Create a virtual environment (e.g., named `venv`):
```bash
python -m venv venv
```

### 2. Activate the Virtual Environment

- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
  (If you encounter an execution policy error, you might need to run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` and then try activating again.)

- **Windows (Command Prompt):**
  ```cmd
  .\venv\Scripts\activate.bat
  ```

- **macOS / Linux (bash/zsh):**
  ```bash
  source venv/bin/activate
  ```
Your terminal prompt should now indicate that you are in the virtual environment (e.g., `(venv) C:\Users\Fernado\Desktop\AIMS-website>`).

### 3. Install Dependencies
With the virtual environment activated, install the required Python packages from the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

### 4. Set Google Cloud Credentials
You need to set an environment variable to point to your Google Cloud service account JSON key file.
Assuming your key file is named `macro-dolphin-432908-t4-1257da99b275.json` and is in the project root directory:

- **Windows (PowerShell) - for the current session:**
  ```powershell
  $env:GOOGLE_APPLICATION_CREDENTIALS="macro-dolphin-432908-t4-1257da99b275.json"
  ```

- **Windows (Command Prompt) - for the current session:**
  ```cmd
  set GOOGLE_APPLICATION_CREDENTIALS=macro-dolphin-432908-t4-1257da99b275.json
  ```

- **macOS / Linux (bash/zsh) - for the current session:**
  ```bash
  export GOOGLE_APPLICATION_CREDENTIALS="macro-dolphin-432908-t4-1257da99b275.json"
  ```
*Note: If your key file is in a different location or has a different name, adjust the path accordingly.*

### 5. Run the Flask Application
Navigate to the directory containing the Flask app if you are not already there (though `app.py` is expected to be run from the project root or have paths adjusted):
The application script is `latest/audio/app.py`. To run it from the project root:
```bash
python latest/audio/app.py
```
You should see output indicating the Flask development server is running, typically on `http://127.0.0.1:5000/`.

### 6. Access the Application
Open your web browser and navigate to:
[http://127.0.0.1:5000/latest/index.html](http://127.0.0.1:5000/latest/index.html)
(Or simply [http://127.0.0.1:5000/](http://127.0.0.1:5000/) if the root route in `app.py` correctly serves `index.html` from the `latest` directory).

### Deactivating the Virtual Environment
When you are done working on the project, you can deactivate the virtual environment:
```bash
deactivate
