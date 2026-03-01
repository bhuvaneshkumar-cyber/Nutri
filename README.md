# NUtri-INO

NUtri-INO is an intelligent, Python-based health and nutrition management platform. Designed for the modern user, it combines a sleek UI with an AI-driven backend to provide personalised dietary insights and health tracking.

---

# Key Features

* AI-Driven Analytics: Utilise the `ai_engine.py` to get smart recommendations based on your dietary habits and health metrics.
* Comprehensive Health Tracking: Manage macros, calories, and fitness goals via the `health_manager.py` logic.
* Modern UI/UX: A clean, responsive interface powered by **NiceGUI** with custom styling defined in `theme.py`.
* Modular Architecture: Clean separation of concerns between AI logic, data management, and the user interface.

# Tech Stack

* Backend: Python 3.x
* Web Framework: Flask / NiceGUI
* AI Engine: Integrated AI analysis module
* Environment: Optimised for Windows (MinGW/Python environment)

# Repository Structure

```text
├── main.py              # Entry point for the application
├── ai_engine.py         # AI logic and health prediction algorithms
├── health_manager.py    # Logic for managing user profiles and nutrition data
├── theme.py             # UI configuration and custom styling
├── requirements.txt     # Project dependencies (to be added)
└── README.md            # Documentation
