#!/usr/bin/env python
# coding: utf-8

import os

import pandas as pd

from Cleaning_Processing.config import DATA_DIR as base_dir

# Load data
all_programs = pd.read_csv(os.path.join(base_dir, "new_programs.csv"), sep="|")
all_programs["id"] = all_programs["id"].astype(str)

# Food-related subcategories
food_subcats = [
    "Free Meals", "Affordable Fresh Food", "Community Garden", "Emergency Food",
    "Food Delivery", "Food Pantry", "Help Pay for Food", "Nutrition Education"
]

food_keywords = (
        "food|meal|pantry|nutrition|garden|dinner|lunch|grocer|breakfast|snack|feed|comida|"
        "aliment|despensa|cena|mandado|lonche|almuerzo|jardin"
    )

# Normalize subcats: lowercase and remove extra whitespace
all_programs["subcats_clean"] = all_programs["subcats"].str.upper().str.replace(r"\s+", " ", regex=True)

# Build pattern: match if any food subcategory appears in subcats (partial match is okay)
food_pattern = '|'.join([fs.upper() for fs in food_subcats])

# Filter programs that contain at least one food-related subcategory
cleaned_programs = all_programs[all_programs["subcats_clean"].str.contains(food_pattern, na=False) | all_programs["name"].str.contains(food_keywords, case=False)]

# Optional: drop helper column
cleaned_programs = cleaned_programs.drop(columns="subcats_clean")
all_programs = all_programs.drop(columns="subcats_clean")

# Print results
print("\nAll Programs:", len(all_programs))
print("Filtered (Food-Related) Programs:", len(cleaned_programs), "\n")

cleaned_programs["zipcode"] = cleaned_programs["zipcode"].astype(str).str.strip()
cleaned_programs["zipcode"] = cleaned_programs["zipcode"].str.replace(r"\.0$", "", regex=True)  # Remove ".0"

#cleaned_programs = cleaned_programs[cleaned_programs["zipcode"].str.lower().isin(["nan", "none"]) == False]   # Remove "nan"/"none"
#print(cleaned_programs.info())
#cleaned_programs.to_csv("new_food_programs.csv", index=False, sep="|")
#print(cleaned_programs["zipcode"])