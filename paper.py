import csv
from hashlib import sha256, sha1
from typing import List

import requests
from bs4 import BeautifulSoup

import requests
import os
import json

from tqdm import tqdm

from extractor import PaperExtractor


class Paper:

    FOLDER = "data/papers/"

    def __init__(self, event, name, url):
        self.name = name
        self.url = url
        self.event = event
        self.path = f"{Paper.FOLDER}{event}/{self.name}.pdf"
        self.authors = self.get_authors()
        self.authors, self.establishments = self.get_authors_affiliations(self.authors)

    def download(self):
        # Send a GET request to the URL
        response = requests.get(self.url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Save the PDF to the specified folder
            with open(self.path, "wb") as f:
                f.write(response.content)
        else:
            raise Exception(f"Failed to download: {self.url} (status-code={response.status_code})")

    def get_authors(self) -> List[str]:
        page = requests.get(self.url.replace(".pdf", ".html"))
        soup = BeautifulSoup(page.content, "html.parser")
        return [a.strip() for a in str(soup.find("h5").contents[0]).split(",")]

    def get_path(self):
        if os.path.exists(self.path):
            return self.path
        else:
            self.download()
            return self.path

    def get_authors_affiliations(self, authors: List[str]):
        return PaperExtractor(self.get_path(), authors).get_authors_affiliations_locations()


if __name__ == '__main__':
    with open("data/links.json") as f:
        links = json.load(f)

    main_data = {}
    locations = [["Hash", "Name", "Latitude", "Longitude"]]
    authors = [["Hash", "Name"]]

    for i, (paper_id, link) in tqdm(enumerate(links.items()), total=len(links)):
        try:
            paper = Paper("interspeech23", paper_id, link)
        except Exception:
            continue
g
        # print(paper.authors, paper.establishments)

        for a in paper.authors:
            authors.append([hash(a), a])

        for e in paper.establishments:
            locations.append([hash(e), e, None, None])

        main_data[paper_id] = {hash(a): [hash(paper.establishments[i - 1]) for i in locs if i < len(paper.establishments)] for a, locs in paper.authors.items()}

    with open('output/general.json', 'w') as outfile:
        json.dump(main_data, outfile, indent=4)

    with open('output/authors.csv', 'w') as outfile:
        csvWriter = csv.writer(outfile, delimiter=',')
        csvWriter.writerows(authors)

    with open('output/locations.csv', 'w') as outfile:
        csvWriter = csv.writer(outfile, delimiter=',')
        csvWriter.writerows(locations)
