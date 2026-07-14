import os

# Directory the cleaning/gap-score pipeline reads raw data from.
# Defaults to the bundled synthetic sample data so the project runs
# end-to-end with no real SACRD data present. Point SACRD_DATA_DIR at a
# real ``Data/`` folder (same layout) to run against real data instead.
_here = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get(
    "SACRD_DATA_DIR",
    os.path.join(_here, "..", "Data", "sample_data"),
)
