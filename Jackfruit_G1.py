

FILE_PATH = r"C:\Users\2025\Desktop\jackfruit\medicine_database(4).xlsx"

import time, re, math, os
from pathlib import Path
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def timing(fn):
    def wrapped(*a, **k):
        t0 = time.time()
        r = fn(*a, **k)
        t1 = time.time()
        print(f"[{fn.__name__}] {t1-t0:.4f}s")
        return r
    return wrapped

def normalize_text(s):
    if s is None: return ""
    s = str(s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokens(s):
    s = normalize_text(s)
    parts = re.split(r"[,\s]+", s)
    return [p for p in parts if len(p) > 1]


def load_dataset(path):
    df = pd.read_excel(path, engine="openpyxl")
    if "Medicine" not in df.columns or "Symptoms" not in df.columns:
        raise ValueError("Excel must have 'Medicine' and 'Symptoms' columns")
    df = df.reset_index(drop=True)
    df["_tokens"] = df["Symptoms"].fillna("").apply(lambda s: set(tokens(s)))
    return df

@timing
def find_prescription(query, df):
    q_list = tokens(query)
    q_set = set(q_list)
    if len(q_set) == 0:
        return {"error": "No valid symptoms/disease tokens found in input."}

    matched_counts = df["_tokens"].apply(lambda s: len(q_set & s)).to_numpy(dtype=float)
    denom = float(len(q_set))
    coverage = matched_counts / (denom if denom > 0 else 1.0)

    full_idx = np.where(coverage == 1.0)[0].tolist()

    result = {"query_tokens": sorted(list(q_set)), "primary": None, "alternatives": [], "leftover": [], "supplement": {}}

    if full_idx:
        primary_idx = int(min(full_idx))
        result["primary"] = {
            "Medicine": df.at[primary_idx, "Medicine"],
            "Symptoms": df.at[primary_idx, "Symptoms"],
            "coverage": float(coverage[primary_idx])
        }
        for idx in full_idx:
            if int(idx) != primary_idx:
                result["alternatives"].append({
                    "Medicine": df.at[int(idx), "Medicine"],
                    "Symptoms": df.at[int(idx), "Symptoms"],
                    "coverage": float(coverage[int(idx)])
                })
        result["leftover"] = []
        return result

    max_cov = float(np.max(coverage)) if coverage.size > 0 else 0.0
    if max_cov <= 0:
        return {"error": "No medicines matched the provided symptoms."}

    best_indices = np.where(coverage == max_cov)[0]
    primary_idx = int(np.min(best_indices))
    primary_tokens = df.at[primary_idx, "_tokens"]
    matched_by_primary = sorted(list(q_set & primary_tokens))

    result["primary"] = {
        "Medicine": df.at[primary_idx, "Medicine"],
        "Symptoms": df.at[primary_idx, "Symptoms"],
        "coverage": float(max_cov),
        "matched_tokens": matched_by_primary
    }

    leftover = sorted(list(q_set - primary_tokens))
    result["leftover"] = leftover

    supplement = {}
    for sym in leftover:
        mask = df["_tokens"].apply(lambda s: sym in s)
        candidates = []
        for idx in df[mask].index.tolist():
            if int(idx) == primary_idx:
                continue
            candidates.append({
                "Medicine": df.at[int(idx), "Medicine"],
                "Symptoms": df.at[int(idx), "Symptoms"]
            })
        supplement[sym] = candidates

    result["supplement"] = supplement
    return result

def compute_bmi(weight_kg, height_cm):
    try:
        h_m = float(height_cm) / 100.0
        if h_m <= 0: return None
        bmi = float(weight_kg) / (h_m * h_m)
        return round(bmi, 1)
    except Exception:
        return None

def bmi_category(bmi):
    if bmi is None:
        return "Unknown"
    if bmi < 18.5: return "Underweight"
    if bmi < 25: return "Normal"
    if bmi < 30: return "Overweight"
    return "Obese"

def severity_to_freq_duration(sev):
    if sev <= 3:
        return 1, 3
    if sev <= 6:
        return 2, 5
    if sev <= 8:
        return 3, 7
    return 4, 10

def classify_severity(sev):
    if sev <= 3:
        return "low"
    if sev <= 6:
        return "normal"
    return "high"

def assign_strength_from_bmi_severity(bmi, severity):
    sev_level = classify_severity(severity)
    if bmi is None:
        bmi_group = "normal"
    elif bmi < 25:
        bmi_group = "low_norm"
    elif bmi < 30:
        bmi_group = "norm_high"
    else:
        bmi_group = "high_plus"

    
    if bmi_group == "low_norm":
        if sev_level == "high":
            return 500
        else:
            return 250
    if bmi_group == "norm_high":
        if sev_level == "high":
            return 650
        else:
            return 500
    
    if bmi_group == "high_plus":
        if sev_level == "high":
            return 650
        else:
            return 500
    
    return 500
def get_diet_plan(bmi, goal, diet_type):
    if bmi is None:
        return "BMI unknown. Cannot generate diet plan."

    if goal == "lose":
        base = "Calorie deficit, high protein, moderate carbs, high fiber."
    else:
        base = "Calorie surplus, high protein, higher carbs, healthy fats."

    diets = {
        "nonveg": [
            "Breakfast: Eggs, oats, black coffee",
            "Lunch: Grilled chicken/fish + vegetables + rice/roti",
            "Dinner: Chicken/fish soup + salad",
            "Snacks: Boiled eggs, nuts, yogurt"
        ],
        "veg": [
            "Breakfast: Oats, poha, paneer, fruits",
            "Lunch: Dal + vegetables + rice/roti",
            "Dinner: Paneer/soy curry + salad",
            "Snacks: Fruits, nuts, sprouts"
        ],
        "vegan": [
            "Breakfast: Oats + almond milk + fruits",
            "Lunch: Lentils + vegetables + rice",
            "Dinner: Tofu/soy + greens",
            "Snacks: Nuts, seeds, hummus"
        ]
    }

    return (
        f"=== DIET PLAN ({goal.upper()}) ===\n"
        f"BMI: {bmi}\n"
        f"{base}\n\n"
        + "\n".join(diets[diet_type]) +
        "\n\nWater: 3–4 liters/day\nAvoid sugar & processed foods.")


def create_and_open_notepad(text, suggested_filename=None):
    try:
        now = time.strftime("%Y%m%d_%H%M%S")
        filename = suggested_filename if suggested_filename else f"prescription_{now}.txt"
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.cwd()
        full = desktop / filename
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            os.startfile(str(full))
        except Exception:
            print("Prescription saved to:", full)
        return str(full)
    except Exception as e:
        print("Failed to create/open notepad:", e)
        return None


class PrescriptionGUI:
    def __init__(self, root):
        self.root = root
        root.title("Prescription Helper — assigned dose (250/500/650)")
        root.geometry("1200x820")

       
        try:
            self.df = load_dataset(FILE_PATH)
            ds_text = f"Loaded: {FILE_PATH} ({len(self.df)} rows)"
        except Exception as e:
            self.df = pd.DataFrame(columns=["Medicine", "Symptoms", "_tokens"])
            ds_text = f"Default not loaded: {e}"

        
        top = ttk.Frame(root); top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text=ds_text, font=("Segoe UI", 10)).pack(side="left", anchor="w")
        ttk.Button(top, text="Browse Excel", command=self.browse).pack(side="right")

        
        input_frame = ttk.LabelFrame(root, text="Enter disease / symptoms and patient info", padding=12)
        input_frame.pack(fill="x", padx=10, pady=(8,12))

        ttk.Label(input_frame, text="Disease / Symptoms:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.entry = ttk.Entry(input_frame, width=80, font=("Segoe UI", 11))
        self.entry.grid(row=0, column=1, columnspan=5, sticky="ew", padx=6, pady=6)
        self.entry.bind("<Return>", lambda e: self.on_prescribe())

        ttk.Label(input_frame, text="Age (years):", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.age_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.age_var, width=10, font=("Segoe UI", 10)).grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(input_frame, text="Weight (kg):", font=("Segoe UI", 10)).grid(row=1, column=2, sticky="w", padx=6)
        self.weight_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.weight_var, width=10, font=("Segoe UI", 10)).grid(row=1, column=3, sticky="w", padx=6)

        ttk.Label(input_frame, text="Height (cm):", font=("Segoe UI", 10)).grid(row=1, column=4, sticky="w", padx=6)
        self.height_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.height_var, width=10, font=("Segoe UI", 10)).grid(row=1, column=5, sticky="w", padx=6)

        ttk.Label(input_frame, text="Severity (1–10):", font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.sev_var = tk.IntVar(value=5)
        sev_scale = ttk.Scale(input_frame, from_=1, to=10, variable=self.sev_var, orient="horizontal", length=360)
        sev_scale.grid(row=2, column=1, columnspan=3, sticky="w", padx=6)

        btns = ttk.Frame(input_frame)
        btns.grid(row=3, column=0, columnspan=6, sticky="w", padx=6, pady=(8,4))
        ttk.Button(btns, text="Get Prescription", command=self.on_prescribe).pack(side="left", padx=(0,8))
        ttk.Button(btns, text="Clear", command=self.clear_output).pack(side="left", padx=(0,8))
        ttk.Button(btns, text="Save Prescription", command=self.on_save_prescription).pack(side="left")

      
        out_frame = ttk.Frame(root); out_frame.pack(fill="both", expand=True, padx=10, pady=6)

        left = ttk.LabelFrame(out_frame, text="Primary Prescription", padding=10)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        self.primary_text = tk.Text(left, width=70, height=18, wrap="word", font=("Segoe UI", 11))
        self.primary_text.pack(fill="both", expand=True, padx=6, pady=6)

        right = ttk.LabelFrame(out_frame, text="Supplementary Medicines (for leftover symptoms)", padding=10)
        right.pack(side="left", fill="both", expand=True)
        self.supp_text = tk.Text(right, width=60, height=30, wrap="word", font=("Segoe UI", 11))
        self.supp_text.pack(fill="both", expand=True, padx=6, pady=6)

        bottom = ttk.LabelFrame(root, text="Patient metrics & Dosing suggestion (illustrative)", padding=10)
        bottom.pack(fill="x", padx=10, pady=(6,12))
        self.metrics_text = tk.Text(bottom, height=8, wrap="word", font=("Segoe UI", 11))
        self.metrics_text.pack(fill="x", padx=6, pady=6)
        ttk.Button(bottom, text="Get Diet Plan", command=self.open_diet_window).pack(pady=5)
        self.diet_text = tk.Text(root, height=12, wrap="word")
        self.diet_text.pack(fill="x", padx=10, pady=10)

        disclaimer = ("Disclaimer: This tool provides illustrative suggestions only. "
                      "It is NOT medical advice. Consult a qualified healthcare professional.")
        ttk.Label(root, text=disclaimer, foreground="red", wraplength=1160, justify="left", font=("Segoe UI", 9)).pack(padx=10, pady=(0,6))
        self.status = ttk.Label(root, text="Ready", font=("Segoe UI", 10))
        self.status.pack(fill="x", padx=10, pady=(0,8))

        self.last_prescription = None

    def browse(self):
        p = filedialog.askopenfilename(title="Select Excel file", filetypes=[("Excel files","*.xlsx;*.xls")])
        if not p:
            return
        try:
            self.df = load_dataset(p)
            self.status.config(text=f"Loaded {p} ({len(self.df)} rows)")
        except Exception as e:
            messagebox.showerror("Load error", str(e))
            self.status.config(text=f"Load failed: {e}")

    def clear_output(self):
        self.primary_text.delete("1.0", "end")
        self.supp_text.delete("1.0", "end")
        self.metrics_text.delete("1.0", "end")
        self.diet_text.delete("1.0","end")
        self.status.config(text="Cleared")
        self.last_prescription = None

    def on_prescribe(self):
        q = self.entry.get().strip()
        danger_symptoms = {
            "chest", "angina", "arrhythmia", "breathlessness",
            "convulsions", "clot", "copd", "aspergillosis",
            "bleeding", "stroke", "syncope", "tachycardia"
            }

        query_tokens = set(tokens(q))

        if query_tokens & danger_symptoms:
            messagebox.showerror(
                "EMERGENCY WARNING",
                "🚨 RED-FLAG SYMPTOMS DETECTED\n\n"
                "These symptoms may indicate a serious or life-threatening condition.\n"
                "Seek EMERGENCY MEDICAL CARE immediately.\n\n"
                "This program cannot generate a prescription for these symptoms."
            )
            return

        res = find_prescription(q, self.df)
        try:
            age_val = int(self.age_var.get())
        except:
            age_val = None

        if age_val is not None and age_val < 15:
            messagebox.showerror(
            "Age Restriction",
            "❌ This program cannot be used for patients under 15.\n"
            "The application will now close."
            )
            self.root.destroy()
            return
        if not q:
            messagebox.showinfo("Input required", "Please enter disease name or symptoms.")
            return
        res = find_prescription(q, self.df)
        self.primary_text.delete("1.0", "end")
        self.supp_text.delete("1.0", "end")
        self.metrics_text.delete("1.0", "end")

        if "error" in res:
            self.primary_text.insert("end", f"Error: {res['error']}\n")
            self.status.config(text=res["error"])
            return

        prim = res.get("primary")
        if prim:
            lines = []
            lines.append(f"Primary medicine: {prim['Medicine']}")
            lines.append(f"Symptoms in sheet: {prim.get('Symptoms','')}")
            lines.append(f"Coverage of your input: {prim.get('coverage',0):.2f}")
            if "matched_tokens" in prim and prim["matched_tokens"]:
                lines.append(f"Matched tokens: {', '.join(prim['matched_tokens'])}")
            self.primary_text.insert("end", "\n".join(lines) + "\n")
        else:
            self.primary_text.insert("end", "No primary medicine found.\n")

        leftover = res.get("leftover", [])
        if not leftover:
            self.supp_text.insert("end", "Primary medicine covers all provided symptoms. No supplementary medicines required.\n")
        else:
            self.supp_text.insert("end", f"Leftover symptoms not covered by primary: {', '.join(leftover)}\n\n")
            self.supp_text.insert("end", "Suggested medicines for each leftover symptom:\n")
            for sym, meds in res.get("supplement", {}).items():
                if not meds:
                    self.supp_text.insert("end", f" - {sym}: No medicine in database specifically lists this symptom.\n")
                else:
                    meds_list = [f"{m['Medicine']}" for m in meds[:8]]
                    self.supp_text.insert("end", f" - {sym}: {', '.join(meds_list)}\n")
        
        age_str = self.age_var.get().strip()
        weight_str = self.weight_var.get().strip()
        height_str = self.height_var.get().strip()
        severity = int(self.sev_var.get())

        try:
            age =int(age_str) if age_str else None
        except:
            age = None
        try:
            weight = float(weight_str) if weight_str else None
        except:
            weight = None
        try:
            height = float(height_str) if height_str else None
        except:
            height = None

        bmi = compute_bmi(weight, height) if (weight and height) else None
        bmi_cat = bmi_category(bmi)

        freq, days = severity_to_freq_duration(severity)
        assigned_strength = assign_strength_from_bmi_severity(bmi, severity)

       
        met_lines = []
        met_lines.append(f"Age: {age if age is not None else 'unknown'} years")
        met_lines.append(f"Weight: {weight if weight is not None else 'unknown'} kg")
        met_lines.append(f"Height: {height if height is not None else 'unknown'} cm")
        met_lines.append(f"BMI: {bmi if bmi is not None else 'unknown'} ({bmi_cat})")
        met_lines.append(f"Severity (1-10): {severity}")
        met_lines.append("")
        met_lines.append("Assigned dosing (illustrative):")
        met_lines.append(f" - Tablet strength assigned: {assigned_strength} mg")
        met_lines.append(f" - Frequency: {freq} time(s) per day")
        met_lines.append(f" - Approx duration: {days} days")
        met_lines.append("")
        met_lines.append("Note: This is an approximate suggestion. Consult a clinician for exact dosing.")

        self.metrics_text.insert("end", "\n".join(met_lines))
        self.status.config(text="Prescription generated (assigned strength shown)")
        self.primary_text.insert(
            "end",
            "\n⚠ General Advice: This tool cannot replace medical diagnosis.\n"
            "If symptoms worsen, last more than 48 hours, or new symptoms develop,\n"
            "please consult a qualified doctor.\n"
            )

        
        self.last_prescription = {
            "query": q,
            "primary": prim,
            "leftover": leftover,
            "supplement": res.get("supplement", {}),
            "age": age,
            "weight": weight,
            "height": height,
            "bmi": bmi,
            "bmi_cat": bmi_cat,
            "severity": severity,
            "assigned_strength": assigned_strength,
            "freq": freq,
            "days": days,
            "diet": self.diet_text.get("1.0","end").strip(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def on_save_prescription(self):
        if not self.last_prescription:
            messagebox.showinfo("No prescription", "Generate a prescription first (Get Prescription) before saving.")
            return
        p = self.last_prescription
        lines = []
        lines.append("=== Prescription ===")
        lines.append(f"Generated: {p['timestamp']}")
        lines.append("")
        lines.append(f"Input disease / symptoms: {p['query']}")
        lines.append("")
        prim = p.get("primary")
        if prim:
            lines.append("Primary medicine:")
            lines.append(f"  - {prim.get('Medicine')}")
            lines.append(f"  - Symptoms (sheet): {prim.get('Symptoms','')}")
            lines.append(f"  - Coverage: {prim.get('coverage',0):.2f}")
            if "matched_tokens" in prim and prim["matched_tokens"]:
                lines.append(f"  - Matched tokens: {', '.join(prim['matched_tokens'])}")
        else:
            lines.append("Primary medicine: None found")

        lines.append("")
        lines.append("User / Patient info:")
        lines.append(f"  - Age: {p['age'] if p['age'] is not None else 'unknown'} years")
        lines.append(f"  - Weight: {p['weight'] if p['weight'] is not None else 'unknown'} kg")
        lines.append(f"  - Height: {p['height'] if p['height'] is not None else 'unknown'} cm")
        lines.append(f"  - BMI: {p['bmi'] if p['bmi'] is not None else 'unknown'} ({p['bmi_cat']})")
        lines.append(f"  - Severity (1-10): {p['severity']}")
        lines.append("")
        lines.append("Assigned dosing (illustrative):")
        lines.append(f"  - Tablet strength assigned: {p['assigned_strength']} mg")
        lines.append(f"  - Frequency: {p['freq']} time(s) per day")
        lines.append(f"  - Approx duration: {p['days']} days")
        lines.append("")
        if p['leftover']:
            lines.append("Leftover symptoms and suggested supplementary medicines:")
            for sym, meds in p['supplement'].items():
                if not meds:
                    lines.append(f"  - {sym}: No medicine in database specifically lists this symptom.")
                else:
                    meds_list = [m['Medicine'] for m in meds[:8]]
                    lines.append(f"  - {sym}: {', '.join(meds_list)}")
        else:
            lines.append("Primary medicine covers all provided symptoms. No supplementary medicines required.")
        lines.append("\n=== DIET PLAN ===")

        diet_now = self.diet_text.get("1.0", "end").strip()
        if diet_now:
            lines.append(diet_now)
        else:
            lines.append("No diet plan generated.")

        lines.append("\n=== END ===")

        content = "\n".join(lines)

        fname = "Prescription_And_Diet_" + time.strftime("%Y%m%d_%H%M%S") + ".txt"
        saved = create_and_open_notepad(content, fname)

        saved = create_and_open_notepad(content, suggested_filename=fname)
        if saved:
            messagebox.showinfo("Saved", f"Prescription saved and opened:\n{saved}")
        else:
            messagebox.showinfo("Saved", "Prescription saved (path shown in console)")
    def open_diet_window(self):
        win = tk.Toplevel(self.root)
        win.title("Diet Planner")
        win.geometry("350x300")

        ttk.Label(win, text="Goal:").pack()
        goal = tk.StringVar(value="lose")
        ttk.Radiobutton(win, text="Lose", variable=goal, value="lose").pack(anchor="w")
        ttk.Radiobutton(win, text="Gain", variable=goal, value="gain").pack(anchor="w")

        ttk.Label(win, text="Diet Type:").pack(pady=5)
        diet = tk.StringVar(value="nonveg")
        ttk.Radiobutton(win, text="Non-Veg", variable=diet, value="nonveg").pack(anchor="w")
        ttk.Radiobutton(win, text="Veg", variable=diet, value="veg").pack(anchor="w")
        ttk.Radiobutton(win, text="Vegan", variable=diet, value="vegan").pack(anchor="w")

        ttk.Button(win, text="Generate", command=lambda:self.generate_diet(goal.get(), diet.get())).pack(pady=10)

    def generate_diet(self, goal, diet_type):
        try:
            bmi = compute_bmi(float(self.weight_var.get()), float(self.height_var.get()))
        except:
            bmi = None

        plan = get_diet_plan(bmi, goal, diet_type)
        self.diet_text.delete("1.0","end")
        self.diet_text.insert("end", plan)


if __name__ == "__main__":
    root = tk.Tk()
    app = PrescriptionGUI(root)
    root.mainloop()
