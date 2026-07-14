import os
import sys

# Add the SACRD root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from Cleaning_Processing.CleaningPrograms import cleaned_programs
from Cleaning_Processing.MonthlyInteraction import combined_interactions_df, combined_shares_df
from Cleaning_Processing.config import DATA_DIR

# Fill missing Zipcodes using program Zipcodes
def fill_zipcodes(df, programs_df):
    df = df.merge(
    programs_df[["id", "zipcode"]].rename(columns={"id": "entity_id", "zipcode": "program_zipcode"}),
    on="entity_id", how="left")

    df["zipcode"] = df.get("zipcode", pd.NA)

    original_non_null = df["zipcode"].notna().sum()
    df["zipcode"] = df["zipcode"].fillna(df["program_zipcode"])
    filled_count = df["zipcode"].notna().sum() - original_non_null
    print(f"Filled {filled_count} missing Zipcodes from programs.")
    df.drop(columns=["program_zipcode"], inplace=True)
    return df
        
def get_gap_scores(interactions, shares, programs, population_df, share_weight=10.0, time_series=False):
    interactions = fill_zipcodes(interactions, programs)
    shares = fill_zipcodes(shares, programs)

    # Make sure the counts are not duplicated
    if "interaction_count" in interactions.columns:
        interactions = interactions.drop(columns=["interaction_count"])
    if "share_count" in shares.columns:
        shares = shares.drop(columns=["share_count"])

    interactions.rename(columns={"event_count": "interaction_count"}, inplace=True)
    shares.rename(columns={"event_count": "share_count"}, inplace=True)

    if time_series:
        interactions["month"] = pd.to_datetime(interactions["date"]).dt.to_period("M").astype(str)
        shares["month"] = pd.to_datetime(shares["date"]).dt.to_period("M").astype(str)

        inter_demand = interactions.groupby(["zipcode", "month"])["interaction_count"].sum().reset_index()
        share_demand = shares.groupby(["zipcode", "month"])["share_count"].sum().reset_index()

        df = pd.merge(inter_demand, share_demand, on=["zipcode", "month"], how="outer").fillna(0)
        df["raw_demand"] = df["interaction_count"] + share_weight * df["share_count"]

        df = df.merge(population_df, on="zipcode", how="left")
        df["population"] = df["population"].replace(0, pd.NA)
        df["demand_score"] = (df["raw_demand"] / df["population"]) * 1000

        program_counts = programs.groupby("zipcode").size().reset_index(name="program_count")
        df = df.merge(program_counts, on="zipcode", how="left")
        df["program_count"] = df["program_count"].fillna(0)

        # Calculate Gap Score
        #df["gap_score"] = df["demand_score"] / (1 + df["program_count"])
        df["gap_score"] = df["demand_score"] / (1 + np.log1p(df["program_count"]))

        return df

    else:
        inter_demand = interactions.groupby("zipcode")["interaction_count"].sum().reset_index()
        share_demand = shares.groupby("zipcode")["share_count"].sum().reset_index()

        df = pd.merge(inter_demand, share_demand, on="zipcode", how="outer").fillna(0)
        df["raw_demand"] = df["interaction_count"] + share_weight * df["share_count"]

        df = df.merge(population_df, on="zipcode", how="left")
        df["population"] = df["population"].replace(0, pd.NA)
        df["demand_score"] = (df["raw_demand"] / df["population"]) * 1000

        program_counts = programs.groupby("zipcode").size().reset_index(name="program_count")
        df = df.merge(program_counts, on="zipcode", how="left")
        df["program_count"] = df["program_count"].fillna(0)

        #df["gap_score"] = df["demand_score"] / (1 + df["program_count"])
        df["gap_score"] = df["demand_score"] / (1 + np.log1p(df["program_count"]))

        return df

# Read zipcode population data
zips_path = os.path.join(DATA_DIR, "External_Data", "zips_external.csv")
zips_external = pd.read_csv(zips_path)
zips_external["Zipcode"] = zips_external["Zipcode"].astype(str)

# Normalize all columns to lowercase for easier merging
for df in [combined_interactions_df, combined_shares_df, cleaned_programs, zips_external]:
    df.columns = df.columns.str.strip().str.lower()

# Get the gap_scores
gap_scores = get_gap_scores(combined_interactions_df, combined_shares_df, cleaned_programs, zips_external, time_series=False)
gap_scores_with_time = get_gap_scores(combined_interactions_df, combined_shares_df, cleaned_programs, zips_external, time_series=True)

# Ensure month is datetime
gap_scores_with_time["month"] = pd.to_datetime(gap_scores_with_time["month"])

# Generate full ZIP × MONTH grid
all_zipcodes = gap_scores_with_time["zipcode"].unique()
all_months = pd.date_range(
    start=gap_scores_with_time["month"].min(),
    end=gap_scores_with_time["month"].max(),
    freq="MS"
)

full_index = pd.MultiIndex.from_product(
    [all_zipcodes, all_months],
    names=["zipcode", "month"]
).to_frame(index=False)

# Merge full grid with actual data
gap_scores_with_time = (
    full_index
    .merge(gap_scores_with_time, on=["zipcode", "month"], how="left")
    .sort_values(["zipcode", "month"])
)

# Fill static fields with ffill + bfill per ZIP
static_fields = ["population", "latitude", "longitude", "program_count"]
gap_scores_with_time[static_fields] = (
    gap_scores_with_time
    .groupby("zipcode")[static_fields]
    .transform(lambda x: x.ffill().bfill())
)

# Fill missing time-varying values with 0
for col in ["interaction_count", "share_count", "raw_demand", "demand_score", "gap_score"]:
    if col in gap_scores_with_time.columns:
        gap_scores_with_time[col] = gap_scores_with_time[col].fillna(0)

# Drop rows with no population 
gap_scores = gap_scores[gap_scores["zipcode"].isin(zips_external["zipcode"])]
gap_scores_with_time = gap_scores_with_time[gap_scores_with_time["zipcode"].isin(zips_external["zipcode"])]

# Drop Default Zipcode (if needed)
gap_scores = gap_scores[~gap_scores["zipcode"].isin(["78205"])]
gap_scores_with_time = gap_scores_with_time[~gap_scores_with_time["zipcode"].isin(["78205"])]

print("\nTop Gap Scores For Whole Year")
print(gap_scores.sort_values(by="gap_score", ascending=False))
print("Mean:", gap_scores["gap_score"].dropna().mean())
print("Median:", gap_scores["gap_score"].dropna().median())

print("\nTop Gap Scores Over Time")
print(gap_scores_with_time.sort_values(by="gap_score", ascending=False))

# Convert gap_score to numeric, coercing errors
gap_scores_with_time["gap_score"] = pd.to_numeric(gap_scores_with_time["gap_score"], errors="coerce")

# Compute average gap score and other metrics per ZIP code
avg_gap_scores = (
    gap_scores_with_time
    .groupby("zipcode", as_index=False)
    .agg({
        "interaction_count": "mean",
        "share_count": "mean",
        "raw_demand": "mean",
        "latitude": "first",
        "longitude": "first",
        "population": "first",           # Assumed constant per ZIP
        "demand_score": "mean",
        "program_count": "first",        # Assumed constant per ZIP
        "gap_score": "mean"
    })
)

# Sort and display
print("\nAverage Monthly Gap Scores:")
print(avg_gap_scores.sort_values(by="gap_score", ascending=False))
print("Mean gap score:", avg_gap_scores["gap_score"].dropna().mean())
print("Median gap score:", avg_gap_scores["gap_score"].dropna().median())

# Optional: Save all
# gap_scores.to_csv("gap_scores.csv", index=False)
# gap_scores_with_time.to_csv("gap_scores_with_time.csv", index=False)
# avg_gap_scores.to_csv("avg_gap_scores.csv", index=False)
