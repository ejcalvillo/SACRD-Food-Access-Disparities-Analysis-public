import os
import glob
import pandas as pd

from Cleaning_Processing.config import DATA_DIR as base_dir

def combine_csv(file_name):
    file_list = glob.glob(os.path.join(base_dir, "**", file_name), recursive=True)
    print(f"Found {len(file_list)} files matching {file_name}")
    if not file_list:
        raise FileNotFoundError(f"No files found for {file_name} in {base_dir}")
    df_list = [pd.read_csv(file) for file in file_list]
    combined_df = pd.concat(df_list, ignore_index=True)
    return combined_df