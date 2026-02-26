import json
import os
import random
from datetime import datetime, timedelta

class HealthManager:
    def __init__(self, storage_file="user_data.json"):
        self.storage_file = storage_file
        self.default_data = {
            "name": "",
            "location": "",
            "target": 2200,
            "consumed": 0,
            "protein": 0,
            "carbs": 0,
            "fats": 0,
            "burned": 0,
            "steps": 0,
            "last_sync": "Never",
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "goal": "🏋️ Strength & Recovery", 
            "target_weight": "70.0",
            "active_strain": "",     # NEW: Stores the current physical strain
            "recovery_mode": False,  # NEW: Toggles the dashboard into rehab mode
            "history": {},
            "progress_log": []
        }
        self.data = self.load_data()
        self._check_daily_reset()

    def load_data(self):
        if not os.path.exists(self.storage_file):
            return self.default_data.copy()
        try:
            with open(self.storage_file, 'r') as f:
                loaded = json.load(f)
                return {**self.default_data, **loaded}
        except:
            return self.default_data.copy()

    def save_data(self):
        with open(self.storage_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def update_profile(self, name, location, goal, target_weight):
        self.data["name"] = name
        self.data["location"] = location
        self.data["goal"] = goal
        self.data["target_weight"] = target_weight
        self.save_data()

    # --- NEW: Rehab & Recovery Methods ---
    def set_recovery_mode(self, strain_description):
        self.data["active_strain"] = strain_description
        self.data["recovery_mode"] = True if strain_description else False
        self.save_data()

    def clear_recovery_mode(self):
        self.data["active_strain"] = ""
        self.data["recovery_mode"] = False
        self.save_data()
    # -------------------------------------

    def log_progress(self, filename, weight):
        self.data["progress_log"].append({
            "date": datetime.now().strftime("%b %d, %Y"),
            "image": filename,
            "weight": weight
        })
        self.save_data()
        
    def get_progress_log(self):
        return self.data.get("progress_log", [])

    def delete_progress_entry(self, filename):
        self.data["progress_log"] = [
            entry for entry in self.data.get("progress_log", []) 
            if entry.get("image") != filename
        ]
        self.save_data()

    def _check_daily_reset(self):
        today = datetime.now().strftime("%Y-%m-%d")
        last_date = self.data.get("current_date")
        
        if last_date != today:
            if last_date:
                if "history" not in self.data:
                    self.data["history"] = {}
                self.data["history"][last_date] = {
                    "consumed": self.data.get("consumed", 0),
                    "protein": self.data.get("protein", 0),
                    "carbs": self.data.get("carbs", 0),
                    "fats": self.data.get("fats", 0),
                    "steps": self.data.get("steps", 0)
                }
            self.force_reset_today()

    def force_reset_today(self):
        self.data["consumed"] = 0
        self.data["protein"] = 0
        self.data["carbs"] = 0
        self.data["fats"] = 0
        self.data["burned"] = 0
        self.data["steps"] = 0
        self.data["current_date"] = datetime.now().strftime("%Y-%m-%d")
        self.save_data()

    def sync_smartwatch(self):
        self._check_daily_reset()
        new_steps = random.randint(50, 500)
        new_burn = int(new_steps * 0.04)
        self.data["steps"] += new_steps
        self.data["burned"] += new_burn
        self.data["last_sync"] = datetime.now().strftime("%H:%M:%S")
        self.save_data()
        return {"steps": new_steps, "burned": new_burn}

    def log_meal(self, food_name, calories, protein, carbs, fats):
        self._check_daily_reset()
        self.data["consumed"] += int(calories)
        self.data["protein"] += int(protein)
        self.data["carbs"] += int(carbs)
        self.data["fats"] += int(fats)
        self.save_data()

    def get_stats(self):
        self._check_daily_reset()
        remaining = max(0, (self.data["target"] + self.data["burned"]) - self.data["consumed"])
        return {**self.data, "remaining": remaining}

    def get_weekly_history(self):
        self._check_daily_reset()
        history_data = self.data.get("history", {})
        dates = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        weekly_stats = {"dates": [], "consumed": [], "protein": [], "carbs": [], "fats": []}
        
        for d in dates:
            stats = self.data if d == self.data["current_date"] else history_data.get(d, {"consumed": 0, "protein": 0, "carbs": 0, "fats": 0})
            clean_date = datetime.strptime(d, "%Y-%m-%d").strftime("%b %d")
            weekly_stats["dates"].append(clean_date)
            weekly_stats["consumed"].append(stats.get("consumed", 0))
            weekly_stats["protein"].append(stats.get("protein", 0))
            weekly_stats["carbs"].append(stats.get("carbs", 0))
            weekly_stats["fats"].append(stats.get("fats", 0))
            
        return weekly_stats