#!/usr/bin/env python
# coding: utf-8

import os
import re

import pandas as pd
from Cleaning_Processing.CleaningInteraction import clean_interaction_df, clean_share_df
from Cleaning_Processing.CleaningPrograms import all_programs, cleaned_programs
from Cleaning_Processing.config import DATA_DIR as base_dir

# Discover month folders (YYYY-MM) instead of hardcoding a fixed date range,
# so this works against either the real Data/ folder or the bundled sample data.
monthly_folders = sorted(
    d for d in os.listdir(base_dir)
    if re.match(r"^\d{4}-\d{2}$", d) and os.path.isdir(os.path.join(base_dir, d))
)

# Separate lists to hold cleaned DataFrames
all_interactions = []
all_shares = []

for month in monthly_folders:
    print(f"Processing {month}...")

    interaction_path = os.path.join(base_dir, month, "interaction.csv")
    share_path = os.path.join(base_dir, month, "share.csv")

    # Process interaction file
    if os.path.exists(interaction_path):
        interaction_df = pd.read_csv(interaction_path)
        cleaned_interaction_df = clean_interaction_df(interaction_df)
        cleaned_interaction_df["Date"] = month
        
        # # Filter numeric and program entity IDs
        cleaned_interaction_df = cleaned_interaction_df[cleaned_interaction_df["Entity_ID"].astype(str).str.isnumeric()]
        cleaned_interaction_df['Entity_ID'] = cleaned_interaction_df['Entity_ID'].astype(str)

        all_interactions.append(cleaned_interaction_df)
    else:
        print(f"Interaction file not found: {interaction_path}, skipping...")

    # Process share file
    if os.path.exists(share_path):
        share_df = pd.read_csv(share_path)
        cleaned_share_df = clean_share_df(share_df)
        cleaned_share_df["Date"] = month
        
        # Filter numeric and program entity IDs
        cleaned_share_df = cleaned_share_df[cleaned_share_df["Entity_ID"].astype(str).str.isnumeric()]
        all_shares.append(cleaned_share_df)
    else:
        print(f"Share file not found: {share_path}, skipping...")

# Combine all months separately
combined_interactions_df = pd.concat(all_interactions, ignore_index=True)
combined_shares_df = pd.concat(all_shares, ignore_index=True)

print(f"\nTotal rows in combined interactions: {len(combined_interactions_df)}")
print(f"Total rows in combined shares: {len(combined_shares_df)}")

print("\nInteraction Entity_ID in cleaned_programs", len(combined_interactions_df[combined_interactions_df["Entity_ID"].isin(cleaned_programs["id"])]))
print("Share Entity_ID in cleaned_programs", len(combined_shares_df[combined_shares_df["Entity_ID"].isin(cleaned_programs["id"])]), "\n")

# Interactions and Shares that are not part of a food program; Program offered food previously?
# print("Inters not in:", combined_interactions_df["Entity_ID"][~combined_interactions_df["Entity_ID"].isin(cleaned_programs["id"])].unique())
# print("Shares not in:", combined_shares_df["Entity_ID"][~combined_shares_df["Entity_ID"].isin(cleaned_programs["id"])].unique())

combined_interactions_df = combined_interactions_df[combined_interactions_df["Entity_ID"].isin(cleaned_programs["id"])]
combined_shares_df = combined_shares_df[combined_shares_df["Entity_ID"].isin(cleaned_programs["id"])]