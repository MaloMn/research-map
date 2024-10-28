from typing import Tuple, Optional, List, Dict
import requests
import json

from tqdm import tqdm
import polars as pl

from secrets import GOOGLE_MAPS_API_KEY


def get_merged_data(conference: str) -> Dict:
    with open(f"output/{conference}/general.json") as f:
        data = json.load(f)

    with open(f"data/papers/{conference}.json") as f:
        manual = json.load(f)

    # adding manually transcribed papers
    for key, value in manual.items():
        data[key] = value

    return data

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


def remove_doubles(strings):
    output = []
    for a in strings:
        found = False
        for b in set(strings).difference({a}):
            if a in b:
                found = True
                break

        if not found:
            output.append(a)

    return output


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


def generate_markers(locations: pl.DataFrame, general):
    output = {}
    for row in locations.rows(named=True):
        if row["Latitude"] is not None:

            papers = []
            for paper in general.values():
                authors_at_location = []
                other_authors = []

                for author, aff in paper["authors"].items():
                    if row["Location"] in aff:
                        authors_at_location.append(author)
                    else:
                        other_authors.append(author)

                if len(authors_at_location) > 0:
                    papers.append({
                        "url": paper["url"],
                        "title": paper["title"],
                        "authors": [f"<strong>{author}</strong>" if author in authors_at_location else author for author in paper["authors"].keys()],
                    })

            output[row["Location"]] = []
            output[row["Location"]].append([row["Longitude"], row["Latitude"]])
            output[row["Location"]].append(papers)

        # TODO Deal with overlapping coordinates

    return output

if __name__ == '__main__':
    data = get_merged_data("interspeech23")
    #
    # locations = sorted(set([c for a in data.values() for b in a.values() for c in b]))
    # locations = remove_doubles(locations)
    #
    # # geocode(locations)
    #
    # with open("output/interspeech23/latitudes.json", "r") as f:
    #     latitudes = json.load(f)
    #     values = [a for a in latitudes.values() if a is not None]
    #     print(sum(values) / len(values))
    # #
    # with open("output/interspeech23/longitudes.json", "r") as f:
    #     longitudes = json.load(f)
    #     values = [a for a in longitudes.values() if a is not None]
    #     print(sum(values) / len(values))
    #
    # coordinates = [(loc, latitudes[loc], longitudes[loc]) for loc in locations]
    #
    # export(coordinates)

    df = pl.read_csv("output/interspeech23/locations.csv")
    with open("output/interspeech23/coordinates.json", "w+") as f:
        json.dump(generate_markers(df, data), f)

