import json
import polars as pl
from tqdm import tqdm

from conference import Conference


class ReverseIndex:

    def __init__(self, conference: str):
        self.conference = conference
        self.locations = pl.read_csv(f"data/locations/*.csv").drop_nulls()
        self.affiliations = Conference(conference).get_merged_data()

        self.output = None

    def reverse(self):
        output = {}
        aggregation = (self.locations
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
                            "authors": [f"<strong>{author}</strong>" if author in authors_at_location else author for
                                        author in paper["authors"].keys()],
                        })

            output[json.dumps(coordinates)] = locations

        self.output = output

        return self

    def export(self):
        with open(f'output/{self.conference}/coordinates.json', "w+") as f:
            json.dump(self.output, f)


if __name__ == '__main__':
    ReverseIndex("interspeech23").reverse().export()
