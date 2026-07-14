#Reusable cleaning code for each month interaction

import os

# Setup base directory and load data
script_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.join(script_dir, "./Data")

import pandas as pd
from Cleaning_Processing.Read_CSV import combine_csv
from Cleaning_Processing.CleaningPrograms import cleaned_programs

def clean_interaction_df(interaction_df):

    # Clean interaction_df
    interaction_df.drop(columns=["Event count.1"], inplace=True)
    interaction_df.rename(columns={
        'Entity type': 'Entity_type',
        'Entity ID': 'Entity_ID',
        'Event count': 'Event_count'
    }, inplace=True)

    # Clean interactions: only SACRD URLs, exclude iframes, normalize 'prog' to 'program'
    cleaned_interactions = interaction_df[
        interaction_df["URL"].str.contains("sacrd", na=False)
    ].copy()
    cleaned_interactions = cleaned_interactions[cleaned_interactions["Entity_type"] != "iframe"]
    cleaned_interactions["Entity_type"] = cleaned_interactions["Entity_type"].replace("prog", "program")

    # # Define food-related search keywords
    food_keywords = (
        "food|meal|pantry|nutrition|garden|dinner|lunch|grocer|breakfast|snack|feed|comida|"
        "aliment|despensa|cena|mandado|lonche|almuerzo|jardin"
    )

    # # All food-related URLs except orgs
    all_food = cleaned_interactions[
        cleaned_interactions["URL"].str.contains(food_keywords, case=False, na=False)
        & (cleaned_interactions["Entity_type"] != "org")
    ].copy()

    # Program interactions with matching Entity_IDs from programs_df
    prog_interactions = cleaned_interactions[
        (cleaned_interactions["Entity_type"] == "program")
        & (cleaned_interactions["Entity_ID"].astype(str).isin(cleaned_programs["id"]))
    ].copy()

    # Add program interactions not already in all_food
    merged = prog_interactions.merge(all_food, how='left', indicator=True)
    new_program_rows = merged[merged["_merge"] == "left_only"].drop(columns="_merge")
    all_food = pd.concat([all_food, new_program_rows], ignore_index=True)

    # Ensure Entity_ID is numeric
    all_food = all_food[all_food["Entity_ID"].astype(str).str.isnumeric()]
    all_food["Zipcode"] = all_food["URL"].str.extract(r"(?i)zipcode=(\d{5})")

    return all_food

def clean_share_df(share_df):

    # Drop duplicate event count column and rename
    share_df = share_df.drop(columns=["Event count.1"])
    share_df = share_df.rename(columns={
        'Entity type': 'Entity_type',
        'Entity ID': 'Entity_ID',
        'Event count': 'Event_count'
    })

    # Food program subcategories
    programs = ["Free Meals", "Affordable Fresh Food", "Community Garden", "Emergency Food", "Food Delivery", "Food Pantry", "Help Pay for Food", "Nutrition Education"]
    programs_pattern = '|'.join([p.lower() for p in programs])

    food_entity_id = cleaned_programs["id"].astype(str).tolist()

    import re
    pattern = r'https?://(www\.)?sacrd\.org[^\s]*'
    new_share_df = share_df[share_df["URL"].str.contains("sacrd", regex=True, na=False)]
    new_share_df


    #Checking for food sub category names in the URL

    url_subcat_pattern = "|".join(p.lower().replace(" ", r"[\s-]*") for p in programs)
    subcat_share_df = new_share_df[new_share_df["URL"].str.contains(url_subcat_pattern, case=False, na=False)]
    subcat_share_df


    #Separating all the urls with the word search

    searches = new_share_df[new_share_df['URL'].str.contains('search', case=False, na=False)]
    no_searches = new_share_df[~new_share_df['URL'].str.contains('search', case=False, na=False)]


    #Finding the common english search words and putting them in a df

    searches_eng_df = searches[searches["URL"].str.contains("food|meal|pantry|nutrition|garden|dinner|lunch|grocer|breakfast|snack|feed", case=False, na=False)]


    #Finding the common spanish search words and putting them in a df

    searches_es_df = searches[searches["URL"].str.contains("aliment|despensa|cena|mandado|lonche|almuerzo|jardin|comida", case=False, na=False)]


    #Adding the initial three df together

    full_share_df = pd.concat([subcat_share_df, searches_eng_df, searches_es_df], ignore_index=True)


    #Taking all of the lines from our full_share_df and removing it
    # from the original new_share_df where we already removed the non sacrd urls

    id_share_sub = new_share_df.merge(full_share_df, how='outer', indicator=True).query('_merge == "left_only"').drop(columns='_merge')


    #Keeping only entity type 'program'
    #Keeping only entity ids that are part of the food programs

    id_share_df = id_share_sub[
        (id_share_sub["Entity_type"] == "program") &
        (id_share_sub["Entity_ID"].astype(str).isin(cleaned_programs["id"].astype(str)))
    ]


    #Updating the full_share_df to now include the id shares
    #These are all our df connected together

    full_share_df = pd.concat([id_share_df, full_share_df], ignore_index=True)

    # Convert both to string
    full_share_df['Entity_ID'] = full_share_df['Entity_ID'].astype(str)
    full_share_df["Zipcode"] = full_share_df["URL"].str.extract(r"(?i)zipcode=(\d{5})")
    #cleanedPrograms_df['id'] = cleanedPrograms_df['id'].astype(str)

    #food_entity_id = cleanedPrograms_df["id"].tolist()
    #no_common_df = full_share_df[~full_share_df['Entity_ID'].isin(food_entity_id)]


    # Merge with indicator
    #filtered_df = full_share_df.merge(no_common_df, how='outer', indicator=True)

    # Keep only rows from full_share_df
    #dropped_share_df = filtered_df[filtered_df['_merge'] == 'left_only'].drop(columns=['_merge'])


    return full_share_df
