# NUtri-INO

**NUtri-INO** is a high-performance health and nutrition dashboard that bridges the gap between computer vision and clinical data science. Powered by **Gemini 2.5 Flash**, it offers a suite of intelligent tools—from identifying food through images to calculating precise portion sizes using linear algebra.

# Advanced Features

* AI Vision Engine: Leverages **Gemini 2.5 Flash** to analyse food images and provide instant JSON-parsed nutritional breakdowns, including calories and macros.
* Algorithmic Meal Prep: Features a custom **Gauss-Jordan Elimination** solver to calculate the exact grams of specific ingredients needed to hit user-defined macro targets.
* Predictive Analytics: Implements linear regression to forecast a 30-day weight trajectory based on logged progress photos and weight entries.
* Lifestyle Correlation Matrix: Uses **Pearson Correlation** to identify hidden patterns, such as how carb intake affects energy levels (steps) or how protein influences total satiety.
* Rehab & Recovery Mode: A specialised module for logging physical strains and generating AI-curated recovery protocols and anti-inflammatory recipes.
* Pantry Alchemist: Analyses images of refrigerators or pantries to "invent" localised recipes using only available ingredients.
* Daily Streak Tracker: Monitors user consistency with a 7-day visual timeline and unbroken login chain calculations.

# Tech Stack

* Backend & UI: Python 3.10+, [NiceGUI](https://nicegui.io/), Flask.
* AI Model: Google Gemini 2.5 Flash (Vision & Chat).
* Styling: Custom "Glassmorphism" UI with glistening text effects.
* Data Handling: Local JSON-based state management with automatic daily resets.

# Repository Structure

```text
├── main.py              # Dashboard UI, Math Algorithms, and Event Handlers
├── ai_engine.py         # Gemini 2.5 Flash API integration
├── health_manager.py    # State Management & Streak Logic
├── theme.py             # Glassmorphism UI Theme & Styling
├── user_data.json       # (Local Storage) User profiles and history
└── progress_shots/      # (Local Storage) Transformation photos
