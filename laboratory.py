from typing import Tuple, Optional, List, Dict
import requests
import json
import csv

from tqdm import tqdm
import polars as pl

from conference import Conference
from secrets import GOOGLE_MAPS_API_KEY


def get_location_coordinates(place_name, api_key) -> Tuple[Optional[float], Optional[float]]:
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={place_name}&key={api_key}"
    # print(url)
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            print("Geocoding failed. Status:", data['status'])
            return None, None
    else:
        print("Failed to retrieve data. Status code:", response.status_code)
        return None, None


def geocode(locations: List[str], save=True):
    latitudes, longitudes = {}, {}
    # latitudes, longitudes = [None for _ in range(len(locations))], [None for _ in range(len(locations))]

    LIMIT = len(locations)

    for loc in tqdm(locations[:LIMIT]):
        # TODO Make a dictionary to store results AND PRINT THEM!!!
        try:
            latitude, longitude = get_location_coordinates(loc, GOOGLE_MAPS_API_KEY)
            latitudes[loc] = latitude
            longitudes[loc] = longitude

            if save:
                with open("output/interspeech23/latitudes.json", "w+") as f:
                    json.dump(latitudes, f, indent=4)

                with open("output/interspeech23/longitudes.json", "w+") as f:
                    json.dump(longitudes, f, indent=4)
        except:
            continue

    return [(loc, latitudes[loc], longitudes[loc]) for loc in locations]


def export(coordinates: List[Tuple[str, float, float]]) -> None:
    df = pl.DataFrame({
        "Location": [loc for loc, _, _ in coordinates],
        "Latitude": [lat for _, lat, _ in coordinates],
        "Longitude": [long for _, _, long in coordinates],
    })

    df.write_csv("output/interspeech23/locations.csv")


class Laboratory:

    DIR = "data/locations/"
    CORRECT_OUTPUT = f"{DIR}/locations.csv"
    ERROR_OUTPUT = f"{DIR}/no-locations.csv"
    ALL_LABS_FILE = f"{DIR}/*.csv"
    COORDINATES = "output/{conference}/coordinates.json"

    def __init__(self, conference: Conference):
        self.conference = conference
        self.correct = pl.read_csv(Laboratory.CORRECT_OUTPUT)
        self.errors = pl.read_csv(Laboratory.ERROR_OUTPUT)

        self.existing = pl.read_csv(Laboratory.ALL_LABS_FILE)
        self.coordinates = Laboratory.COORDINATES.format(conference=conference.name)

        self.affiliations = self.conference.get_merged_affiliations()

    def export(self):

        locations = []
        for paper in self.affiliations.values():
            for labs in paper["authors"].values():
                locations += labs

        locations = sorted(set(locations))

        locations = [[loc, None, None] for loc in locations if loc not in self.existing.get_column("Lab")]
        for i in range(len(locations)):
            for loc in self.existing.get_column("Lab"):
                if locations[i][0] in loc:
                    locations[i][1] = self.existing.filter(pl.col("Lab") == loc).select("Latitude").item()
                    locations[i][2] = self.existing.filter(pl.col("Lab") == loc).select("Longitude").item()
                    break

        with open(Laboratory.CORRECT_OUTPUT, 'a') as f:
            writer = csv.writer(f)
            writer.writerows(locations)

    def pinpoint(self):
        missing_coordinates = self.existing.filter(pl.any_horizontal(pl.all().is_null()))

        for lab in tqdm(missing_coordinates.get_column("Lab")):
            latitude, longitude = get_location_coordinates(lab, GOOGLE_MAPS_API_KEY)

            row = pl.DataFrame({
                "Lab": [lab],
                "Latitude": [latitude],
                "Longitude": [longitude],
            })

            if latitude is not None:
                self.correct = self.correct.vstack(row)
            else:
                self.errors = self.errors.vstack(row)

        self.correct.drop_nulls().write_csv(Laboratory.CORRECT_OUTPUT)
        self.errors.write_csv(Laboratory.ERROR_OUTPUT)

    def compute_reversed_index(self):
        output = {}
        aggregation = (self.existing.drop_nulls()
                       .group_by(["Latitude", "Longitude"])
                       .agg(pl.col("Lab")))

        for row in tqdm(aggregation.rows()):
            coordinates = [float(row[0]), float(row[1])]
            locations = {}

            for lab in row[2]:
                locations[lab] = []
                # Get papers published from this lab
                for paper in self.affiliations.values():
                    authors_at_location = []
                    other_authors = []

                    for author, aff in paper["authors"].items():
                        if lab in aff:
                            authors_at_location.append(author)
                        else:
                            other_authors.append(author)

                    if len(authors_at_location) > 0:
                        locations[lab].append({
                            "url": paper["url"],
                            "title": paper["title"],
                            "authors": [f"<strong>{author}</strong>" if author in authors_at_location else author
                                        for
                                        author in paper["authors"].keys()],
                        })

            if len(locations) > 0:
                output[json.dumps(coordinates)] = locations

        with open(self.coordinates, "w+") as f:
            json.dump(output, f)


if __name__ == '__main__':
    # Laboratory(Conference("interspeech24")).export()
    # Laboratory(Conference("interspeech24")).pinpoint()
    Laboratory(Conference("interspeech24")).compute_reversed_index()
