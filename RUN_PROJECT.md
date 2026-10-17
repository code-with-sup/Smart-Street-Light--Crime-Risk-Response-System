# Run the current Smart Street project

The newer, active project is here ("newer version" is a description, not part of the folder name):

```text
/Users/supriya/Documents/GitHub/Smart Street Light- Crime Risk Response System
```

## Terminal

```bash
cd "/Users/supriya/Documents/GitHub/Smart Street Light- Crime Risk Response System"
./.venv/bin/python run.py
```

The existing virtual environment is already installed and checked. You do not need to reinstall it for each run.
The launcher opens the dashboard. Open http://127.0.0.1:8000/app directly if needed.
Stop the server with **Control+C** in the terminal where you started it.

To run without opening a browser automatically:

```bash
./.venv/bin/python run.py --no-browser
```

## Antigravity IDE

1. Open **Antigravity IDE**, then **File → Open Folder**.
2. Select the GitHub project folder above, not the old iCloud folder or its legacy subfolder.
3. Choose **Terminal → New Terminal** and run:

   ```bash
   ./.venv/bin/python run.py
   ```

Alternatively, choose **Terminal → Run Task → Run Smart Street**. The included `.vscode/tasks.json` selects the project’s own Python interpreter and working directory.
If the Python extension asks for an interpreter, select `.venv/bin/python` inside this project.

On macOS, allow camera access for the app running the terminal if prompted. In **Live monitoring**, plug in the Logitech, refresh **Camera source**, select **C270 HD WEBCAM**, and start the camera.
Use only one running server on port 8000 at a time. If another terminal already runs this project, stop that instance with Control+C before starting again.

## Consolidated files

- `artifacts/`: prototype image, wiring diagrams and screenshots.
- `crimes/`: merged local example videos.
- `Weapon-Detection/` and `ucf-crime/`: merged datasets.
- `models/` and `runs/`: preserved model files and training outputs.
- `legacy-icloud-project/`: older source, packaging files, diagnostics and differing versions; not the application entry point.
- `consolidation-reports/`: local migration log and content-verification records.

The old iCloud project location contains only a small `PROJECT_MOVED.txt` pointer for the previous chat workspace. It is not another copy of the project.
