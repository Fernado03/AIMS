# KINAVIS AI Medical Scribe

## Description

KINAVIS AI Medical Scribe is a web-based application designed to assist medical professionals in generating SOAP (Subjective, Objective, Assessment, Plan) notes. It features audio transcription for subjective notes and leverages Google's Gemini AI (`gemini-2.5-pro-exp-03-25`) for on-demand generation of Assessment, Plan, and clinical Summary sections.

## Features

-   **Audio Recording & Transcription:** For capturing Subjective patient narratives.
-   **Manual Data Entry:** For all SOAP note sections.
-   **AI-Powered Assessment Generation:** Creates an Assessment based on Subjective and Objective data.
-   **AI-Powered Plan Generation:** Creates a Plan based on Subjective, Objective, and Assessment data.
-   **AI-Powered Summary Generation:** Creates a concise clinical summary from the complete S+O+A+P note.
-   **On-Demand Generation:** AI content generation is triggered by explicit "Generate" buttons on relevant pages.
-   **Web-Based Interface:** User-friendly interface with distinct pages for each SOAP note section and summary.
-   **Data Persistence:** Notes are saved in an SQLite database.
-   **Loading Indicators:** Provides user feedback during AI generation processes.
-   **Styled Interface:** Enhanced CSS for better visual experience of text input areas.

## Technology Stack

-   **Frontend:** HTML, CSS, JavaScript
-   **Backend:** Python, Flask
-   **Database:** SQLite
-   **AI Services:**
    -   Google Cloud Speech-to-Text (for audio transcription)
    -   Google Cloud Vertex AI - Gemini `gemini-2.5-pro-exp-03-25` (for S.O.A.P. section generation)

## Setup and Run Instructions

These instructions will guide you through setting up and running the Python Flask backend for the AI Medical Scribe application.

### Prerequisites

-   Python 3.x installed (e.g., Python 3.9+).
-   `pip` (Python package installer) installed.
-   Access to a terminal or command prompt.
-   A Google Cloud Platform (GCP) project with the following APIs enabled:
    -   Cloud Speech-to-Text API
    -   Vertex AI API
-   A Google Cloud service account JSON key file with appropriate permissions (e.g., "Vertex AI User", "Cloud Speech API User", "Storage Object Admin" if using GCS for audio uploads). Download this key file.
-   The GCS bucket name `audio-upload-bucket-fernado` should exist in your GCP project if you intend to use the audio file upload feature for transcription as currently configured in `latest/audio/app.py`.

### 1. Clone the Repository / Navigate to Project Directory
If you have cloned this project from a repository, navigate to its root directory. Otherwise, ensure you are in the main project directory (`AIMS-website`).

Example:
```bash
cd path/to/AIMS-website
```

### 2. Set up a Python Virtual Environment
It's highly recommended to use a virtual environment to manage project dependencies.

Create a virtual environment (e.g., named `venv`):
```bash
python -m venv venv
```

### 3. Activate the Virtual Environment

-   **Windows (PowerShell):**
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```
    (If you encounter an execution policy error, you might need to run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` and then try activating again.)

-   **Windows (Command Prompt):**
    ```cmd
    .\venv\Scripts\activate.bat
    ```

-   **macOS / Linux (bash/zsh):**
    ```bash
    source venv/bin/activate
    ```
Your terminal prompt should now indicate that you are in the virtual environment (e.g., `(venv) C:\Users\Fernado\Desktop\AIMS-website>`).

### 4. Install Dependencies
With the virtual environment activated, install the required Python packages from the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
You need to set environment variables to allow the application to authenticate with Google Cloud and configure Vertex AI.

-   **`GOOGLE_APPLICATION_CREDENTIALS`**:
    Set this to the absolute or relative path of your downloaded Google Cloud service account JSON key file. For example, if you placed `macro-dolphin-432908-t4-1257da99b275.json` in the project root:

    -   Windows (PowerShell) - for the current session:
        ```powershell
        $env:GOOGLE_APPLICATION_CREDENTIALS="macro-dolphin-432908-t4-1257da99b275.json"
        ```
    -   Windows (Command Prompt) - for the current session:
        ```cmd
        set GOOGLE_APPLICATION_CREDENTIALS=macro-dolphin-432908-t4-1257da99b275.json
        ```
    -   macOS / Linux (bash/zsh) - for the current session:
        ```bash
        export GOOGLE_APPLICATION_CREDENTIALS="macro-dolphin-432908-t4-1257da99b275.json"
        ```

-   **`VERTEX_AI_PROJECT_ID`** (Optional, has default):
    Your Google Cloud Project ID. The application defaults to `macro-dolphin-432908-t4` if this is not set.
    ```powershell
    # Example for PowerShell:
    $env:VERTEX_AI_PROJECT_ID="your-gcp-project-id"
    ```

-   **`VERTEX_AI_LOCATION`** (Optional, has default):
    The GCP region for Vertex AI services (e.g., `us-central1`). The application defaults to `us-central1` if this is not set.
    ```powershell
    # Example for PowerShell:
    $env:VERTEX_AI_LOCATION="your-vertex-ai-region"
    ```

### 6. Run the Flask Application
The application script is `latest/audio/app.py`. To run it from the project root directory:
```bash
python latest/audio/app.py
```
The `init_db()` function will be called automatically, creating the `notes_main.db` SQLite database file in the `latest/audio/` directory if it doesn't exist.
You should see output indicating the Flask development server is running, typically on `http://127.0.0.1:5000/`.

### 7. Access the Application
Open your web browser and navigate to the main page, which is typically the subjective notes page to start a new session:
[http://127.0.0.1:5000/latest/subjective.html](http://127.0.0.1:5000/latest/subjective.html)

Alternatively, the index page is:
[http://127.0.0.1:5000/latest/index.html](http://127.0.0.1:5000/latest/index.html)

## Usage Workflow

1.  Start on the **Subjective** page: Record audio or type subjective notes. Click "NEXT" to save and proceed.
2.  **Objective** page: Enter objective findings. Click "NEXT" to save and proceed.
3.  **Assessment** page: Click "Generate Assessment" to have AI populate the assessment based on S+O data. Review/edit. Click "NEXT" to save and proceed.
4.  **Plan** page: Click "Generate Plan" to have AI populate the plan based on S+O+A data. Review/edit. Click "Summarize" (or "NEXT") to save and proceed.
5.  **Summary** page: Click "Generate Summary" to have AI create a clinical summary based on the full S+O+A+P note.

## Project Structure (Simplified)

-   `README.md` (This file)
-   `requirements.txt` (Python dependencies)
-   `cararun.md` (Original run instructions, now largely superseded by this README)
-   `macro-dolphin-432908-t4-1257da99b275.json` (Your GCP service account key - **DO NOT COMMIT THIS TO A PUBLIC REPOSITORY**)
-   `latest/`
    -   `*.html` (Frontend pages: subjective, objective, assessment, plan, summary, index)
    -   `*.css` (CSS files for styling)
    -   `audio/`
        -   `app.py` (Flask backend application)
        -   `script.js` (Client-side JavaScript logic)
        -   `notes_main.db` (SQLite database, created on first run)
    -   `components/` (HTML/CSS components - if any are still actively used)
    -   `public/` (Static assets like images, SVGs)

## Troubleshooting

-   **`sqlite3.OperationalError: table notes has no column named ...`**: This usually means your `latest/audio/notes_main.db` file is outdated.
    1.  Stop the Flask application.
    2.  Delete `latest/audio/notes_main.db`.
    3.  Restart the Flask application. It will recreate the database with the correct schema. (Note: This will erase existing notes).
-   **AI Generation Not Working / Errors:**
    1.  Ensure `GOOGLE_APPLICATION_CREDENTIALS` is correctly set and points to a valid service account key file.
    2.  Verify that the necessary Google Cloud APIs (Vertex AI, Speech-to-Text) are enabled in your GCP project.
    3.  Check the Flask terminal for error messages from `app.py` or the Gemini API.
    4.  Check the browser's developer console for JavaScript errors or failed network requests.
-   **"Generate" buttons unresponsive:**
    1.  Ensure `latest/audio/script.js` is correctly linked in the HTML file for that page.
    2.  Check the browser console for JavaScript errors that might be preventing event listeners from attaching.