from pathlib import Path
from typing import Tuple, Optional, List

from sklearn.cluster import DBSCAN
import numpy as np
import requests
import json
import csv

from tqdm import tqdm
import polars as pl

from conference import Conference
from key import GOOGLE_MAPS_API_KEY


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


def jaccard_similarity(list1, list2):
    intersection = len(list(set(list1).intersection(list2)))
    union = (len(set(list1)) + len(set(list2))) - intersection
    return float(intersection) / union


class Laboratory:

    DIR = "data/locations/"
    CORRECT_OUTPUT = f"{DIR}/locations.csv"
    ALL_LABS_FILE = f"{DIR}/*.csv"
    COORDINATES = "output/{conference}/coordinates.json"

    def __init__(self, conference: Conference):
        self.conference = conference
        self.correct = pl.read_csv(Laboratory.CORRECT_OUTPUT)

        self.existing = pl.read_csv(Laboratory.ALL_LABS_FILE)
        self.coordinates = Laboratory.COORDINATES.format(conference=conference.name)

        self.affiliations = self.conference.get_merged_affiliations()

    def export(self, min_similarity=0.65):
        locations = []
        for paper in self.affiliations.values():
            for labs in paper["authors"].values():
                locations += labs

        locations = sorted(set(locations))

        locations = [[loc, None, None] for loc in locations if loc not in self.existing.get_column("Lab")]
        for i in range(len(locations)):
            for loc in self.existing.get_column("Lab"):
                if jaccard_similarity(locations[i][0], loc) >= min_similarity:
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

            self.correct = self.correct.vstack(row)

        self.correct.drop_nulls().write_csv(Laboratory.CORRECT_OUTPUT)

    def compute_reversed_index(self):
        output = {}
        aggregation = (self.existing.drop_nulls()
                       .group_by(["Latitude", "Longitude"])
                       .agg(pl.col("Lab")))

        placed_papers = set()

        for row in tqdm(aggregation.rows()):
            coordinates = [float(row[0]), float(row[1])]

            if coordinates == [0.0, 0.0]:
                continue

            locations = {}

            for lab in row[2]:
                locations[lab] = []
                # Get papers published from this lab
                for paper_id, paper in self.affiliations.items():
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

                        placed_papers.add(paper_id)

            if sum([len(paper) for paper in locations.values()]) > 0:
                output[json.dumps(coordinates)] = locations

        for paper_id, paper in self.affiliations.items():
            if paper_id not in placed_papers:
                print(f"WARNING: {paper_id} will not appear on the map.")

        with open(self.coordinates, "w+") as f:
            json.dump(output, f)

    def group_lab_names(self, epsilon=0.3):
        labs = self.existing.select("Lab").to_numpy().tolist()
        labs = list(set([a[0] for a in labs]))

        X = None
        if Path("output/jaccard_similarity.csv").exists():
            X = np.loadtxt("output/jaccard_similarity.csv", delimiter=",")

        if X is None or X.shape != (len(labs), len(labs)):
            print("Building distance matrix")
            X = np.array([[0.0 for _ in labs] for _ in labs])
            for i, lab_a in tqdm(enumerate(labs), total=len(labs)):
                for j, lab_b in enumerate(labs[i + 1:]):
                    similarity = jaccard_similarity(lab_a.split(", "), lab_b.split(", "))
                    X[i, i + j + 1] = X[i + j + 1, i] = 1 - similarity

            np.savetxt("output/jaccard_similarity.csv", X, delimiter=",")
        else:
            print("Loaded distance matrix")

        print(X.shape)

        clustering = DBSCAN(eps=epsilon, min_samples=2, metric='precomputed').fit(X)
        print(np.unique(clustering.labels_))

        output = [["Group", "Lab"]]
        for i in np.unique(clustering.labels_):
            if i == -1:
                continue
            for lab in np.array(labs)[clustering.labels_ == i]:
                output.append([i, lab])

        with open("output/lab_groups.csv", 'w+') as f:
            writer = csv.writer(f)
            writer.writerows(output)


if __name__ == '__main__':
    Laboratory(Conference("interspeech24")).export()
    # Laboratory(Conference("interspeech24")).pinpoint()
    Laboratory(Conference("interspeech24")).compute_reversed_index()
    # Laboratory(Conference("interspeech24")).group_lab_names(epsilon=0.35)