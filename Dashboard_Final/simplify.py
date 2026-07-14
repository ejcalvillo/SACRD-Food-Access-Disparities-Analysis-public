import geopandas as gpd

gdf = gpd.read_file("../Dashboard_Final/san_antonio_zipcodes.geojson")
gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.001, preserve_topology=True)
gdf.to_file("simplified.geojson", driver="GeoJSON")
