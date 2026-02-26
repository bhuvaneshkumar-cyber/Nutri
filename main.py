import os
import sys
import math
# --- PYINSTALLER WINDOWED MODE FIX ---
# When running as a windowed .exe, there is no console. 
# Uvicorn tries to write logs to a missing console and crashes. 
# We redirect these missing logs into a dummy "black hole" (os.devnull).
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
# -------------------------------------

import json
import urllib.request
from datetime import datetime, timedelta
from nicegui import ui, app
import asyncio
from health_manager import HealthManager
from ai_engine import analyze_food_image, chat_with_ai, generate_recipe, analyze_pantry_image, generate_recovery_protocol
from theme import apply_theme

# --- INIT & FILE SYSTEM ---
user_health = HealthManager()
apply_theme()

PROGRESS_DIR = 'progress_shots'
if not os.path.exists(PROGRESS_DIR):
    os.makedirs(PROGRESS_DIR)
app.add_static_files('/progress_shots', PROGRESS_DIR)

# --- CONSTANTS & LOGIC ---
GOAL_OPTIONS = ["🔥 Lose Fat", "🥗 Eat Healthy", "🚫 Cut Sugar", "🏋️ Strength & Recovery"]
GOAL_SUGGESTIONS = {
    "🔥 Lose Fat": ["High-Protein Salad Bowl", "Metabolism-Boosting Tea", "Light Lentil Soup"],
    "🥗 Eat Healthy": ["Mixed Veggie Stir-fry", "Fresh Local Fruit Bowl", "Wholesome Grain Wrap"],
    "🚫 Cut Sugar": ["Spiced Yogurt", "Roasted Nuts & Seeds", "Herbal Infusion"],
    "🏋️ Strength & Recovery": ["Post-Workout Protein Shake", "Lean Meat & Sweet Potato", "Protein-Rich Legume Dish"]
}

class State:
    def __init__(self):
        self.scan_result = None
        self.is_scanning = False
        self.chat_input = ""
        self.name = user_health.data.get("name", "")
        self.location = user_health.data.get("location", "")
        self.current_goal = user_health.data.get("goal", "🏋️ Strength & Recovery")
        self.target_weight = str(user_health.data.get("target_weight", "70.0"))
        self.current_weight = "75.0" 
        self.strain_input = ""
        
        display_name = self.name.split()[0] if self.name else "User"
        self.messages = [("NUtri-INO", f"Welcome, {display_name}! Ready to crush the {self.current_goal} plan today?", True)]

state = State()

# --- NEW: MATH ALGORITHM ---
def solve_gauss_jordan(matrix, targets):
    """Solves a 3x3 system of linear equations using Gauss-Jordan elimination."""
    # Create the augmented matrix
    aug = [matrix[i] + [targets[i]] for i in range(3)]
    
    for i in range(3):
        # Find pivot
        pivot = aug[i][i]
        if pivot == 0:
            # Swap rows if pivot is zero
            for j in range(i+1, 3):
                if aug[j][i] != 0:
                    aug[i], aug[j] = aug[j], aug[i]
                    pivot = aug[i][i]
                    break
            if pivot == 0: return None # Singular matrix (foods have identical macro profiles)
            
        # Divide row by pivot
        for j in range(4):
            aug[i][j] /= pivot
            
        # Eliminate other rows
        for k in range(3):
            if k != i:
                factor = aug[k][i]
                for j in range(4):
                    aug[k][j] -= factor * aug[i][j]
                    
    return [aug[0][3], aug[1][3], aug[2][3]]


# Add variables to track the optimizer's state
state.opt_targets = {'p': 50, 'c': 60, 'f': 20}
state.opt_foods = [
    {'name': 'Chicken Breast', 'p': 31, 'c': 0, 'f': 3.6},
    {'name': 'White Rice', 'p': 2.7, 'c': 28, 'f': 0.3},
    {'name': 'Almonds', 'p': 21, 'c': 22, 'f': 50}
]
state.opt_results = ""

def pearson_correlation(x, y):
    """Calculates the linear relationship between two lifestyle variables."""
    n = len(x)
    if n < 3: return 0.0
    
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    # Prevent divide-by-zero if data is entirely flat/identical
    if all(xi == mean_x for xi in x) or all(yi == mean_y for yi in y):
        return 0.0
        
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    sum_sq_x = sum((xi - mean_x)**2 for xi in x)
    sum_sq_y = sum((yi - mean_y)**2 for yi in y)
    
    denominator = math.sqrt(sum_sq_x * sum_sq_y)
    return numerator / denominator if denominator != 0 else 0.0

# --- DIALOGS & ONBOARDING ---

recipe_dialog = ui.dialog()
with recipe_dialog, ui.card().classes('w-full max-w-lg glass-card p-6'):
    recipe_title = ui.label().classes('text-2xl font-black glisten-text mb-4')
    recipe_spinner = ui.spinner('dots', size='2em', color='green').classes('mx-auto my-4')
    recipe_content = ui.markdown().classes('text-green-900 text-sm leading-relaxed')
    ui.button('CLOSE', on_click=recipe_dialog.close, color='green-8').classes('w-full mt-6 shadow-md rounded-lg')

settings_dialog = ui.dialog().props('persistent')
with settings_dialog, ui.card().classes('w-full max-w-sm glass-card p-6'):
    ui.label('Profile Setup').classes('text-xl font-bold accessible-text mb-4')
    input_name = ui.input('Your Name', value=state.name).classes('w-full mb-2').props('outlined color=green-7')
    
    with ui.row().classes('w-full items-center gap-2 mb-4 no-wrap'):
        input_location = ui.input('Location (City, Country)', value=state.location).classes('flex-grow').props('outlined color=green-7')
        
        async def fetch_location():
            try:
                ui.notify("Requesting location permissions...", color='info', icon='place')
                js_code = '''
                    return new Promise((resolve) => {
                        if (!navigator.geolocation) resolve({error: 'Geolocation not supported'});
                        else navigator.geolocation.getCurrentPosition(
                            async (pos) => {
                                try {
                                    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`;
                                    const res = await fetch(url, { headers: { 'Accept-Language': 'en-US,en;q=0.9' }});
                                    const data = await res.json();
                                    resolve({success: true, address: data.address});
                                } catch (err) {
                                    resolve({error: 'Browser could not reach the Maps API.'});
                                }
                            },
                            (err) => resolve({error: 'Location permission was denied.'})
                        );
                    });
                '''
                result = await ui.run_javascript(js_code, timeout=10.0)
                
                if result and result.get('success'):
                    addr = result.get('address', {})
                    city = addr.get('suburb', addr.get('city', addr.get('town', addr.get('county', 'Unknown Area'))))
                    state_region = addr.get('state', '')
                    country = addr.get('country', '')
                    
                    input_location.value = ", ".join(filter(bool, [city, state_region, country]))
                    ui.notify("Location successfully detected!", color='positive', icon='check')
                else:
                    ui.notify(result.get('error', 'Failed to get location'), color='warning')
            except TimeoutError:
                ui.notify("Location request timed out. Please type it manually.", color='negative')
            except Exception as e:
                ui.notify(f"Unexpected error: {str(e)}", color='negative')

        ui.button(icon='my_location', on_click=fetch_location).props('flat round color=green-8').tooltip('Auto-Detect')
    
    ui.label('Health Objectives').classes('text-sm text-green-800 font-bold mb-2 mt-2')
    select_goal = ui.select(options=GOAL_OPTIONS, value=state.current_goal).classes('w-full mb-2').props('outlined color=green-7')
    input_target_weight = ui.input('Target Weight (kg)', value=state.target_weight).classes('w-full mb-6').props('outlined color=green-7')

    def save_settings():
        try:
            val_name = str(input_name.value).strip() if input_name.value is not None else ""
            val_loc = str(input_location.value).strip() if input_location.value is not None else ""
            val_weight_str = str(input_target_weight.value).strip() if input_target_weight.value is not None else ""

            if not val_name or not val_loc or not val_weight_str:
                ui.notify("Please fill out all fields to continue.", color='warning')
                return
                
            try:
                val_weight_float = float(val_weight_str)
            except ValueError:
                ui.notify("Target weight must be a valid number (e.g. 70 or 75.5)", color='negative')
                return
                
            state.name = val_name
            state.location = val_loc
            state.current_goal = select_goal.value
            state.target_weight = str(val_weight_float)
            
            try:
                user_health.update_profile(state.name, state.location, state.current_goal, state.target_weight)
            except TypeError:
                user_health.update_profile(state.name, state.location, state.current_goal)
                user_health.data["target_weight"] = state.target_weight
                user_health.save_data()
            
            profile_sidebar.refresh()
            smart_suggestions.refresh()
            predictive_analytics.refresh() 
            settings_dialog.close()
            ui.notify("Profile securely updated!", color='positive', icon='check_circle')
            
        except Exception as e:
            ui.notify(f"System Error during save: {str(e)}", color='negative', timeout=5000)

    ui.button('SAVE PROFILE', on_click=save_settings, color='green-7').classes('w-full shadow-md rounded-lg')

ui.timer(0.5, lambda: settings_dialog.open() if not state.name else None, once=True)

# --- ASYNC EVENT HANDLERS ---

async def show_recipe(food_name):
    recipe_title.text = f"Curating {food_name}..."
    recipe_content.content = ""
    recipe_spinner.visible = True
    recipe_dialog.open()
    result = await asyncio.to_thread(generate_recipe, food_name, state.location, state.current_goal)
    recipe_title.text = f"🍽️ {food_name}"
    recipe_spinner.visible = False
    recipe_content.content = result

async def handle_pantry_upload(e):
    ui.notify("Alchemist activated! Analyzing fridge...", color="purple", icon="science")
    recipe_title.text = "🧪 The Alchemist is analyzing your ingredients..."
    recipe_content.content = ""
    recipe_spinner.visible = True
    recipe_dialog.open()
    
    try:
        if hasattr(e, 'file'):
            filename = e.file.name.lower()
            content = e.file.read()
        else:
            filename = e.name.lower()
            content = e.content.read()
            
        image_bytes = await content if asyncio.iscoroutine(content) else content
            
        mime_type = "image/jpeg"
        if filename.endswith('.png'): mime_type = "image/png"
        elif filename.endswith('.webp'): mime_type = "image/webp"
        elif filename.endswith(('.heic', '.heif')): mime_type = "image/heic"

        result = await asyncio.to_thread(analyze_pantry_image, image_bytes, state.location, state.current_goal, mime_type)
        
        recipe_title.text = "✨ Your Custom Pantry Recipes"
        recipe_spinner.visible = False
        recipe_content.content = result
    except Exception as ex:
        recipe_title.text = "Analysis Failed"
        recipe_spinner.visible = False
        recipe_content.content = f"**System Error:** {str(ex)}"
    finally:
        smart_suggestions.refresh()

async def sync_watch():
    ui.notify("Syncing with wearable...", color='info')
    await asyncio.sleep(1) 
    updates = user_health.sync_smartwatch()
    stats_panel.refresh()
    weekly_chart.refresh() 
    ui.notify(f"Synced: +{updates['steps']} steps!", color='positive', icon='watch')

def trigger_reset():
    user_health.force_reset_today()
    stats_panel.refresh()
    weekly_chart.refresh()
    ui.notify("Today's data has been reset!", color='warning', icon='refresh')

async def handle_upload(e):
    state.is_scanning = True
    scan_area.refresh()
    try:
        content = e.file.read() if hasattr(e, 'file') else e.content.read()
        image_bytes = await content if asyncio.iscoroutine(content) else content
        result = await asyncio.to_thread(analyze_food_image, image_bytes)
        
        if isinstance(result, dict) and "error" in result:
            state.scan_result = {"error": result.get("message", "API Error occurred.")}
        else:
            state.scan_result = result
    except Exception as ex:
        state.scan_result = {"error": f"Internal Error: {str(ex)}"}
    finally:
        state.is_scanning = False
        scan_area.refresh()

async def handle_progress_upload(e):
    try:
        try:
            weight_val = str(float(state.current_weight))
        except ValueError:
            ui.notify("Please enter a valid number for your weight.", color='negative')
            return

        filename = e.file.name if hasattr(e, 'file') else e.name
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        safe_filename = f"progress_{timestamp}_{filename}"
        filepath = os.path.join(PROGRESS_DIR, safe_filename)
        
        content = e.file.read() if hasattr(e, 'file') else e.content.read()
        image_bytes = await content if asyncio.iscoroutine(content) else content
        
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
            
        user_health.log_progress(safe_filename, weight_val)
        
        progress_gallery.refresh()
        predictive_analytics.refresh() 
        ui.notify("Transformation logged successfully!", color='positive', icon='trending_up')
    except Exception as ex:
        ui.notify(f"Failed to save image: {str(ex)}", color='negative')

async def delete_progress_photo(filename):
    try:
        filepath = os.path.join(PROGRESS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        user_health.delete_progress_entry(filename)
        progress_gallery.refresh()
        predictive_analytics.refresh()
        ui.notify("Photo deleted successfully.", color='info', icon='delete')
    except Exception as ex:
        ui.notify(f"Error deleting photo: {str(ex)}", color='negative')

def log_meal():
    if state.scan_result and "error" not in state.scan_result:
        res = state.scan_result
        user_health.log_meal(res.get('name', 'Food'), res.get('calories', 0), res.get('protein', 0), res.get('carbs', 0), res.get('fats', 0))
        state.scan_result = None
        scan_area.refresh()
        stats_panel.refresh()
        weekly_chart.refresh()
        ui.notify("Meal securely logged!", color='positive', icon='check_circle')


async def send_chat():
    if not state.chat_input.strip(): return
    text = state.chat_input
    state.chat_input = "" 
    state.messages.append(("You", text, False))
    chat_area.refresh()
    
    stats = user_health.get_stats()
    context = f"User: {state.name}. Loc: {state.location}. Goal: {state.current_goal}. Cals: {stats['consumed']}/{stats['target']}."
    
    response = await asyncio.to_thread(chat_with_ai, text, context)
    state.messages.append(("NUtri-INO", response, True))
    chat_area.refresh()

# --- REFRESHABLE UI COMPONENTS ---

@ui.refreshable
def profile_sidebar():
    with ui.card().classes('w-full glass-card p-5 border-t-4 border-green-500 relative'):
        ui.button(icon='settings', on_click=settings_dialog.open).props('flat round color=green-8 size=sm').classes('absolute top-2 right-2')
        with ui.row().classes('items-center gap-3 mb-4 mt-2'):
            ui.icon('account_circle', size='3em', color='green-8')
            with ui.column().classes('gap-0'):
                ui.label(state.name if state.name else "New User").classes('text-lg font-bold accessible-text')
                with ui.row().classes('items-center gap-1'):
                    ui.icon('place', size='14px', color='gray-500')
                    ui.label(state.location if state.location else "Location needed").classes('text-xs text-gray-500 font-medium')
        ui.separator().classes('mb-4 bg-green-900/20')
        ui.label('🎯 ACTIVE GOAL').classes('text-xs font-bold text-green-800 tracking-wider mb-2')
        ui.label(state.current_goal).classes('text-md font-bold text-green-700 bg-white/50 p-2 rounded-lg text-center w-full mb-2 border border-green-200')
        ui.label(f"Target Weight: {state.target_weight} kg").classes('text-xs text-center w-full text-green-800 font-bold mb-2')

@ui.refreshable
def smart_suggestions():
    with ui.column().classes('w-full gap-4'):
        with ui.card().classes('w-full glass-card p-4'):
            ui.label('💡 RECOMMENDED EATS').classes('text-xs font-bold text-green-800 tracking-wider mb-2')
            ui.label('Click for localized recipes!').classes('text-[10px] text-gray-500 mb-3 italic')
            suggestions = GOAL_SUGGESTIONS.get(state.current_goal, [])
            for food in suggestions:
                ui.button(food, on_click=lambda f=food: show_recipe(f), icon='auto_awesome') \
                    .classes('w-full justify-start text-sm text-green-900 bg-white/40 hover:bg-green-100 mb-2 rounded-lg shadow-sm normal-case') \
                    .props('flat')
        
        with ui.card().classes('w-full glass-card p-4 border-l-4 border-purple-500'):
            with ui.row().classes('items-center gap-2 mb-2'):
                ui.icon('kitchen', size='sm', color='purple-600')
                ui.label('PANTRY ALCHEMIST').classes('text-xs font-bold text-purple-800 tracking-wider')
            ui.label("Don't know what to cook? Snap a pic of your open fridge or ingredients.").classes('text-xs text-gray-600 mb-3 leading-tight')
            with ui.card().classes('w-full p-0 overflow-hidden cursor-pointer hover:bg-purple-50 transition-colors shadow-none border border-purple-200'):
                ui.upload(label="📸 SCAN FRIDGE", on_upload=handle_pantry_upload, auto_upload=True, max_files=1) \
                    .props('color=purple-6 flat').classes('w-full')

@ui.refreshable
def stats_panel():
    d = user_health.get_stats()
    with ui.row().classes('w-full grid grid-cols-3 gap-4 mb-4'):
        with ui.card().classes('glass-card p-4 flex flex-col items-center justify-center'):
            ui.label('INTAKE').classes('text-green-800 text-xs font-bold tracking-wide')
            ui.label(f"{d['consumed']}").classes('text-3xl font-bold accessible-text')
            ui.label('kcal').classes('text-xs text-green-700')
        with ui.card().classes('glass-card p-4 flex flex-col items-center justify-center border-2 border-green-400'):
            ui.label('REMAINING').classes('text-green-800 text-xs font-bold tracking-wide')
            ui.label(f"{d['remaining']}").classes('text-4xl font-black glisten-text')
            ui.label('kcal').classes('text-xs text-green-700')
        with ui.card().classes('glass-card p-4 flex flex-col items-center justify-center'):
            ui.label('STEPS').classes('text-green-800 text-xs font-bold tracking-wide')
            ui.label(f"{d['steps']}").classes('text-3xl font-bold accessible-text')
            ui.label('today').classes('text-xs text-green-700')

# --- NEW: ALGORITHMIC MEAL PREP UI ---
@ui.refreshable
def meal_optimizer():
    with ui.column().classes('w-full mt-2'):
        ui.label("Enter your target macros and the nutritional value (per 100g) of 3 ingredients. The algorithm will calculate the perfect portion sizes.").classes('text-xs text-gray-600 mb-2 leading-tight')
        
        # Target Inputs
        with ui.row().classes('w-full gap-2 mb-4'):
            ui.input('Target Protein (g)', value=state.opt_targets['p']).bind_value(state.opt_targets, 'p').classes('flex-grow').props('outlined dense color=orange-7 type=number')
            ui.input('Target Carbs (g)', value=state.opt_targets['c']).bind_value(state.opt_targets, 'c').classes('flex-grow').props('outlined dense color=orange-7 type=number')
            ui.input('Target Fats (g)', value=state.opt_targets['f']).bind_value(state.opt_targets, 'f').classes('flex-grow').props('outlined dense color=orange-7 type=number')

        # Food Inputs
        for i in range(3):
            with ui.row().classes('w-full gap-2 mb-2 items-center'):
                ui.input(f'Food {i+1}', value=state.opt_foods[i]['name']).bind_value(state.opt_foods[i], 'name').classes('w-1/3').props('outlined dense color=orange-7')
                ui.input('P', value=state.opt_foods[i]['p']).bind_value(state.opt_foods[i], 'p').classes('w-1/6').props('outlined dense color=orange-7 type=number')
                ui.input('C', value=state.opt_foods[i]['c']).bind_value(state.opt_foods[i], 'c').classes('w-1/6').props('outlined dense color=orange-7 type=number')
                ui.input('F', value=state.opt_foods[i]['f']).bind_value(state.opt_foods[i], 'f').classes('w-1/6').props('outlined dense color=orange-7 type=number')

        def calculate_portions():
            try:
                # Extract targets
                tp = float(state.opt_targets['p'])
                tc = float(state.opt_targets['c'])
                tf = float(state.opt_targets['f'])
                
                # Build the 3x3 matrix (macros per 1 gram)
                matrix = []
                for f in state.opt_foods:
                    matrix.append([float(f['p'])/100, float(f['c'])/100, float(f['f'])/100])
                
                # Transpose matrix for the equation Ax = b
                A = [[matrix[j][i] for j in range(3)] for i in range(3)]
                b = [tp, tc, tf]
                
                # Run the algorithm
                solution = solve_gauss_jordan(A, b)
                
                if not solution:
                    state.opt_results = "Error: Foods are too nutritionally similar to solve."
                else:
                    g1, g2, g3 = solution
                    # Check for mathematically correct but physically impossible negative weights
                    if g1 < 0 or g2 < 0 or g3 < 0:
                        state.opt_results = "Math Error: Impossible to hit these exact targets without negative food. Try swapping an ingredient!"
                    else:
                        state.opt_results = f"🎯 **Perfect Prep:** \n- {g1:.1f}g of {state.opt_foods[0]['name']} \n- {g2:.1f}g of {state.opt_foods[1]['name']} \n- {g3:.1f}g of {state.opt_foods[2]['name']}"
                
            except ValueError:
                state.opt_results = "Please ensure all macro fields contain valid numbers."
            
            meal_optimizer.refresh()

        ui.button('CALCULATE PERFECT PORTIONS', on_click=calculate_portions, color='orange-7').classes('w-full shadow-md rounded-lg mt-2 font-bold')
        
        if state.opt_results:
            with ui.card().classes('w-full bg-orange-50 border-l-4 border-orange-500 mt-4 p-3'):
                ui.markdown(state.opt_results).classes('text-sm text-orange-900')

@ui.refreshable
def weekly_chart():
    data = user_health.get_weekly_history()
    chart_config = {
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}},
        'legend': {'data': ['Calories', 'Protein', 'Carbs', 'Fats'], 'bottom': 0},
        'grid': {'left': '3%', 'right': '4%', 'bottom': '12%', 'containLabel': True},
        'xAxis': {'type': 'category', 'data': data['dates'], 'axisLabel': {'color': '#1b5e20'}},
        'yAxis': [
            {'type': 'value', 'name': 'Kcal', 'position': 'left', 'axisLabel': {'color': '#4caf50'}, 'splitLine': {'lineStyle': {'color': 'rgba(76, 175, 80, 0.2)'}}},
            {'type': 'value', 'name': 'Macros (g)', 'position': 'right', 'axisLabel': {'color': '#1b5e20'}, 'splitLine': {'show': False}}
        ],
        'series': [
            {'name': 'Calories', 'type': 'bar', 'data': data['consumed'], 'itemStyle': {'color': 'rgba(76, 175, 80, 0.6)', 'borderRadius': [4, 4, 0, 0]}},
            {'name': 'Protein', 'type': 'line', 'yAxisIndex': 1, 'smooth': True, 'data': data['protein'], 'itemStyle': {'color': '#f44336'}, 'symbolSize': 8},
            {'name': 'Carbs', 'type': 'line', 'yAxisIndex': 1, 'smooth': True, 'data': data['carbs'], 'itemStyle': {'color': '#2196f3'}, 'symbolSize': 8},
            {'name': 'Fats', 'type': 'line', 'yAxisIndex': 1, 'smooth': True, 'data': data['fats'], 'itemStyle': {'color': '#ff9800'}, 'symbolSize': 8}
        ]
    }
    ui.echart(chart_config).classes('w-full h-64 mt-2')

# --- NEW: DATA CORRELATION MATRIX ---
@ui.refreshable
def data_insights():
    history = user_health.data.get("history", {})
    today = user_health.data.get("current_date")
    
    # Merge today's live data with history for real-time analysis
    full_data = history.copy()
    full_data[today] = {
        "consumed": user_health.data.get("consumed", 0),
        "protein": user_health.data.get("protein", 0),
        "carbs": user_health.data.get("carbs", 0),
        "fats": user_health.data.get("fats", 0),
        "steps": user_health.data.get("steps", 0)
    }
    
    # Filter out empty days to avoid mathematically skewed data
    valid_days = [d for d in full_data.values() if d.get("consumed", 0) > 0 or d.get("steps", 0) > 0]
    
    if len(valid_days) < 4:
        with ui.card().classes('w-full glass-card p-6 flex flex-col items-center text-center border-dashed border-2 border-indigo-300'):
            ui.icon('hub', size='3em', color='indigo-400').classes('mb-2')
            ui.label("Gathering Intelligence...").classes('text-lg font-bold text-indigo-900')
            ui.label(f"The Correlation Matrix needs at least 4 days of logged data to find hidden lifestyle patterns. Currently logged: {len(valid_days)} days.").classes('text-sm text-indigo-700 mt-2')
        return

    # Extract arrays for the Pearson algorithm
    cals = [d.get("consumed", 0) for d in valid_days]
    steps = [d.get("steps", 0) for d in valid_days]
    carbs = [d.get("carbs", 0) for d in valid_days]
    protein = [d.get("protein", 0) for d in valid_days]
    
    insights = []
    
    # 1. Carbs vs Steps (Energy correlation)
    r_carbs_steps = pearson_correlation(carbs, steps)
    if r_carbs_steps > 0.6:
        insights.append(("🔋 High Energy Pattern", f"Strong positive correlation ({r_carbs_steps:.2f}). On days you eat more carbs, you tend to take significantly more steps!"))
    elif r_carbs_steps < -0.6:
        insights.append(("🛋️ Carb Coma Detected", f"Negative correlation ({r_carbs_steps:.2f}). High carb days are strongly linked to lower step counts. Consider adjusting meal timing."))

    # 2. Protein vs Calories (Satiety correlation)
    r_prot_cals = pearson_correlation(protein, cals)
    if r_prot_cals < -0.5:
        insights.append(("🥩 Satiety Effect", f"Negative correlation ({r_prot_cals:.2f}). Eating more protein is helping you naturally consume fewer total calories."))
        
    # 3. Steps vs Calories (Appetite correlation)
    r_steps_cals = pearson_correlation(steps, cals)
    if r_steps_cals > 0.7:
        insights.append(("🏃 Active Appetite", f"Positive correlation ({r_steps_cals:.2f}). High step days strongly trigger hunger, leading to higher calorie intake. Monitor post-workout snacking."))
        
    with ui.card().classes('w-full glass-card p-4 border-l-4 border-indigo-500'):
        ui.label('LIFESTYLE CORRELATIONS').classes('text-xs font-bold text-indigo-800 tracking-wider mb-2')
        
        if not insights:
            ui.label("Data is currently neutral. No strong lifestyle correlations detected yet. Keep logging!").classes('text-sm text-indigo-900 italic bg-indigo-50 p-2 rounded')
        else:
            for icon_title, text in insights:
                with ui.card().classes('w-full bg-indigo-50 shadow-none border border-indigo-100 p-3 mb-2'):
                    ui.label(icon_title).classes('text-sm font-bold text-indigo-900 mb-1')
                    ui.label(text).classes('text-xs text-indigo-800 leading-tight')

@ui.refreshable
def predictive_analytics():
    log = user_health.get_progress_log()
    
    if len(log) < 2:
        with ui.card().classes('w-full glass-card p-6 flex flex-col items-center justify-center text-center border-dashed border-2 border-blue-300'):
            ui.icon('insights', size='3em', color='blue-400').classes('mb-2')
            ui.label("Data Insufficient").classes('text-lg font-bold text-blue-900')
            ui.label("Log at least 2 progress photos with your weight to unlock the Predictive Data Analytics Console.").classes('text-sm text-blue-700 mt-2')
        return

    try:
        parsed_data = []
        for entry in log:
            try:
                dt = datetime.strptime(entry["date"], "%b %d, %Y")
                w = float(entry["weight"])
                parsed_data.append((dt, w))
            except (ValueError, TypeError):
                continue
                
        if len(parsed_data) < 2: return
            
        parsed_data.sort(key=lambda x: x[0]) 
        start_date = parsed_data[0][0]
        
        xs = [(p[0] - start_date).days for p in parsed_data]
        ys = [p[1] for p in parsed_data]
        
        n = len(xs)
        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xy = sum(x*y for x, y in zip(xs, ys))
        sum_xx = sum(x*x for x in xs)
        
        denominator = (n * sum_xx) - (sum_x ** 2)
        slope = 0 if denominator == 0 else ((n * sum_xy) - (sum_x * sum_y)) / denominator
        intercept = (sum_y - (slope * sum_x)) / n
        
        dates_out = []
        weights_out = []
        projected_dates = []
        projected_weights = []
        
        for x in xs:
            dates_out.append((start_date + timedelta(days=x)).strftime("%b %d"))
            weights_out.append(round((slope * x) + intercept, 1))
            
        last_x = xs[-1]
        for future_x in range(last_x, last_x + 30, 5):
            projected_dates.append((start_date + timedelta(days=future_x)).strftime("%b %d"))
            projected_weights.append(round((slope * future_x) + intercept, 1))
            
        if slope < -0.01:
            trend_text = f"📉 Trending Down: Losing approx {abs(slope*7):.1f} kg per week."
        elif slope > 0.01:
            trend_text = f"📈 Trending Up: Gaining approx {(slope*7):.1f} kg per week."
        else:
            trend_text = "⚖️ Weight is currently stable."

        with ui.card().classes('w-full glass-card p-4 border-l-4 border-blue-500'):
            ui.label('FUTURE TRAJECTORY').classes('text-xs font-bold text-blue-800 tracking-wider mb-2')
            ui.label(trend_text).classes('text-sm font-bold text-blue-900 bg-blue-50 p-2 rounded mb-4')
            
            chart_config = {
                'tooltip': {'trigger': 'axis'},
                'legend': {'data': ['Historical Trend', '30-Day Forecast']},
                'grid': {'left': '3%', 'right': '4%', 'bottom': '5%', 'containLabel': True},
                'xAxis': {
                    'type': 'category', 
                    'boundaryGap': False, 
                    'data': dates_out + projected_dates[1:] 
                },
                'yAxis': {
                    'type': 'value', 
                    'scale': True, 
                    'axisLabel': {'formatter': '{value} kg'}
                },
                'series': [
                    {
                        'name': 'Historical Trend',
                        'type': 'line',
                        'data': weights_out + [None] * (len(projected_dates)-1),
                        'itemStyle': {'color': '#2196f3'},
                        'lineStyle': {'width': 3}
                    },
                    {
                        'name': '30-Day Forecast',
                        'type': 'line',
                        'data': [None] * (len(weights_out)-1) + projected_weights,
                        'itemStyle': {'color': '#ff9800'},
                        'lineStyle': {'type': 'dashed', 'width': 3}
                    }
                ]
            }
            ui.echart(chart_config).classes('w-full h-48')

    except Exception as e:
        ui.label(f"Error calculating trajectory: {e}").classes('text-red-500 text-xs')

@ui.refreshable
def scan_area():
    if state.is_scanning:
        with ui.row().classes('w-full justify-center p-6 glass-card'):
            ui.spinner('audio', size='3em', color='green')
            ui.label("Processing macronutrients...").classes('ml-4 self-center text-green-800 font-medium')
    elif state.scan_result:
        if "error" in state.scan_result:
            with ui.card().classes('w-full glass-card p-4 border-l-4 border-red-500'):
                ui.label("Analysis Failed").classes('text-xl font-bold text-red-600')
                ui.label(state.scan_result["error"]).classes('text-sm text-gray-700 break-words')
                ui.button('DISMISS', on_click=lambda: setattr(state, 'scan_result', None) or scan_area.refresh(), color='red').classes('mt-4 w-full shadow-none')
        else:
            res = state.scan_result
            with ui.card().classes('w-full glass-card p-5 border-l-4 border-green-500 mb-4'):
                ui.label(res.get('name', 'Unknown')).classes('text-2xl font-bold accessible-text')
                with ui.row().classes('w-full justify-between items-center my-2'):
                    ui.label(f"{res.get('calories', 0)} KCAL").classes('text-xl font-black text-green-700')
                    ui.label(f"P:{res.get('protein',0)}g | C:{res.get('carbs',0)}g | F:{res.get('fats',0)}g").classes('text-sm font-medium text-gray-600')
                ui.label(res.get('advice', '')).classes('text-sm italic text-green-800 mb-4 bg-green-50 p-2 rounded')
                with ui.row().classes('w-full gap-3'):
                    ui.button('LOG MEAL', on_click=log_meal, color='green-6').classes('flex-1 shadow-md rounded-lg')
                    ui.button('DISCARD', on_click=lambda: setattr(state, 'scan_result', None) or scan_area.refresh(), color='grey-4').classes('flex-1 text-black shadow-none rounded-lg')
    else:
        with ui.card().classes('w-full glass-card p-0 overflow-hidden cursor-pointer hover:bg-white/50 transition-colors mb-4'):
            ui.upload(label="📸 UPLOAD FOOD TO SCAN", on_upload=handle_upload, auto_upload=True, max_files=1).props('color=green-7 flat').classes('w-full')

@ui.refreshable
def progress_gallery():
    with ui.column().classes('w-full mt-2'):
        with ui.row().classes('w-full gap-4 items-center mb-4'):
            ui.input('Current Weight (kg)', value=state.current_weight).bind_value(state, 'current_weight').classes('w-32').props('outlined dense color=green-7')
            with ui.card().classes('glass-card p-0 overflow-hidden cursor-pointer hover:bg-white/50 flex-grow'):
                ui.upload(label="📸 Upload Progress Shot", on_upload=handle_progress_upload, auto_upload=True, max_files=1).props('color=green-7 flat').classes('w-full')
        
        log = user_health.get_progress_log()
        if not log:
            with ui.row().classes('w-full justify-center p-6 bg-white/30 rounded-lg border border-dashed border-green-400'):
                ui.label("No progress photos yet. Start tracking your transformation today!").classes('text-green-800 italic text-sm font-medium')
        else:
            with ui.row().classes('w-full grid grid-cols-2 sm:grid-cols-3 gap-4'):
                for entry in reversed(log):
                    with ui.card().classes('p-2 glass-card hover:scale-105 transition-transform relative'):
                        ui.button(icon='delete', on_click=lambda f=entry['image']: delete_progress_photo(f)) \
                            .props('flat round color=red size=sm') \
                            .classes('absolute top-3 right-3 z-10 bg-white/80 hover:bg-red-100 backdrop-blur-sm shadow-sm')
                        ui.image(f"/progress_shots/{entry['image']}").classes('w-full h-32 object-cover rounded-md mb-2')
                        with ui.row().classes('w-full justify-between items-center'):
                            ui.label(entry['date']).classes('text-[10px] text-gray-600 font-bold uppercase tracking-wide')
                            ui.label(f"{entry['weight']} kg").classes('text-xs text-white bg-green-600 px-2 py-1 rounded-full font-black')
# --- NEW: REHAB & RECOVERY UI ---

@ui.refreshable
def rehab_panel():
    is_recovering = user_health.data.get("recovery_mode", False)
    active_strain = user_health.data.get("active_strain", "")

    # Visual UI shift when injured
    border_color = 'border-red-500' if is_recovering else 'border-green-500'
    bg_color = 'bg-red-50' if is_recovering else 'bg-white/40'
    text_color = 'text-red-900' if is_recovering else 'text-green-900'

    with ui.card().classes(f'w-full glass-card p-4 border-l-4 {border_color} {bg_color} transition-all'):
        with ui.row().classes('items-center gap-2 mb-2'):
            ui.icon('healing' if is_recovering else 'health_and_safety', size='sm', color='red-600' if is_recovering else 'green-600')
            ui.label('RECOVERY & REHAB').classes(f'text-xs font-bold {text_color} tracking-wider')

        if is_recovering:
            ui.label(f"Active Focus: {active_strain}").classes('text-sm font-bold text-red-800 mb-2')
            ui.label("The AI is currently curating your suggestions for optimal tissue repair.").classes('text-xs text-gray-600 mb-4')
            
            async def load_protocol():
                recipe_title.text = "⚕️ Generating Clinical Protocol..."
                recipe_content.content = ""
                recipe_spinner.visible = True
                recipe_dialog.open()
                result = await asyncio.to_thread(generate_recovery_protocol, active_strain, state.location)
                recipe_title.text = f"Recovery: {active_strain}"
                recipe_spinner.visible = False
                recipe_content.content = result

            with ui.row().classes('w-full gap-2'):
                ui.button('VIEW PROTOCOL', on_click=load_protocol, color='red-6').classes('flex-grow shadow-md')
                
                def clear_injury():
                    user_health.clear_recovery_mode()
                    rehab_panel.refresh()
                    ui.notify("Recovery mode cleared. Back to normal training!", color='positive')
                    
                ui.button(icon='check_circle', on_click=clear_injury, color='green-6').props('round flat bg-color=white')
        else:
            ui.label("Log an injury or muscle strain to adapt your diet for tissue recovery.").classes('text-xs text-gray-600 mb-3 leading-tight')
            ui.input('What hurts? (e.g. Lower back stiffness)', value=state.strain_input).bind_value(state, 'strain_input').classes('w-full mb-2').props('outlined dense color=red-7')
            
            def set_injury():
                if state.strain_input.strip():
                    user_health.set_recovery_mode(state.strain_input)
                    state.strain_input = "" # clear input
                    rehab_panel.refresh()
                    ui.notify("Dashboard shifted into Recovery Mode.", color='warning', icon='healing')
                    
            ui.button('ACTIVATE RECOVERY MODE', on_click=set_injury, color='red-7').classes('w-full shadow-sm normal-case text-xs')

@ui.refreshable
def chat_area():
    with ui.column().classes('w-full gap-3'):
        for name, text, is_ai in state.messages:
            bg_color = 'green-1' if is_ai else 'green-7'
            text_color = 'black' if is_ai else 'white'
            ui.chat_message(text=text, name=name, sent=not is_ai) \
                .props(f'bg-color="{bg_color}" text-color="{text_color}"')


# --- DASHBOARD LAYOUT ---

# --- DASHBOARD LAYOUT ---

with ui.row().classes('w-full justify-between items-center py-4 px-6 mb-2 bg-white/30 backdrop-blur-md shadow-sm'):
    ui.label('NUtri-INO').classes('text-3xl font-black glisten-text tracking-tight')
    with ui.row().classes('gap-2'):
        ui.button(icon='restart_alt', on_click=trigger_reset).props('flat round color=orange-8 size=md').tooltip('Reset Today')
        ui.button(icon='watch', on_click=sync_watch).props('flat round color=green-8 size=lg').tooltip('Sync Wearable')

with ui.row().classes('w-full max-w-7xl mx-auto flex-wrap lg:flex-nowrap gap-6 p-4 items-stretch'):
    
    # LEFT COLUMN (Strictly Profile & Navigation)
    with ui.column().classes('w-full lg:w-1/4 gap-4'):
        profile_sidebar()
        rehab_panel()
        with ui.expansion('Data Matrix', icon='hub', value=True).classes('w-full glass-card text-indigo-900 font-bold bg-white/40 border-l-4 border-indigo-500'):
            data_insights()

    # CENTER COLUMN (Core Engine: Stats, Charts, and Analytics)
    with ui.column().classes('w-full lg:w-2/4 gap-4'):
        stats_panel()
        scan_area()
        
        # 1. SWAPPED: Weekly Trends moved to the top
        with ui.expansion('Weekly Trends', icon='insert_chart', value=True).classes('w-full glass-card text-green-900 font-bold bg-white/40'):
            weekly_chart()
            
        # 2. SWAPPED: Predictive Analytics moved down
        with ui.expansion('Predictive Analytics', icon='online_prediction', value=False).classes('w-full glass-card text-blue-900 font-bold bg-white/40 border-l-4 border-blue-500'):
            predictive_analytics()
            
        with ui.expansion('Algorithmic Meal Prep', icon='calculate', value=False).classes('w-full glass-card text-orange-900 font-bold bg-white/40 border-l-4 border-orange-500'):
            meal_optimizer()
            
        with ui.expansion('Body Transformation', icon='photo_camera', value=False).classes('w-full glass-card text-green-900 font-bold bg-white/40'):
            progress_gallery()

    # RIGHT COLUMN (AI Assistant & Recipes)
    with ui.column().classes('w-full lg:w-1/4 gap-4 flex flex-col'):
        smart_suggestions()
        with ui.card().classes('w-full glass-card flex-grow flex flex-col p-0 overflow-hidden min-h-[400px]'):
            with ui.scroll_area().classes('flex-grow p-4 bg-white/20'):
                chat_area()
            with ui.row().classes('w-full p-3 bg-white/60 border-t border-white/50 gap-2 items-center backdrop-blur-md'):
                ui.input(placeholder='Ask your coach...').props('dense outlined rounded color=green-7').classes('flex-grow bg-white') \
                    .bind_value(state, 'chat_input').on('keydown.enter', send_chat)
                ui.button(icon='send', on_click=send_chat, color='green-6').props('round shadow-md')

ui.run(title="NUtri-INO Dashboard", dark=False, port=8080, reload=False)