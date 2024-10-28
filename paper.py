from typing import List, Tuple
from pathlib import Path
import requests
import json
import os

from Levenshtein import distance
from bs4 import BeautifulSoup
from tqdm import tqdm

from extractor import PaperExtractor

def get_closest_from_list(initial: str, targets: List[str]):
    distances = [distance(initial, t) for t in targets]
    return targets[distances.index(min(distances))]


class Paper:

    FOLDER = "data/papers/"

    def __init__(self, event, name, url):
        self.name = name
        self.url = url
        self.page_url = self.url.replace(".pdf", ".html")

        self.event = event
        self.path = f"{Paper.FOLDER}{event}/{self.name}.pdf"
        self.page_path = self.path.replace(".pdf", ".html")

        self.authors_reference, self.title = self.get_reference()
        self.authors_affiliations = self.get_authors_affiliations()
        self.fix_authors_names_from_reference()

    def download(self):
        # Send a GET request to the URL
        response = requests.get(self.url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Save the PDF to the specified folder
            with open(self.path, "wb") as f:
                f.write(response.content)
        else:
            raise ImportError(f"Failed to download: {self.url} (status-code={response.status_code})")

    def get_reference(self) -> Tuple[List[str], str]:
        if os.path.exists(self.page_path):
            with open(self.page_path, "r") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
        else:
            page = requests.get(self.page_url)

            with open(self.page_path, "wb+") as f:
                f.write(page.content)

            soup = BeautifulSoup(page.content, "html.parser")

        authors = [" ".join(meta["content"].split(",")[::-1]).strip() for meta in soup.findAll("meta", attrs={"name": "citation_author"})]
        title = soup.findAll("meta", attrs={"name": "citation_title"})[0]["content"]

        return authors, title

    def get_path(self):
        if os.path.exists(self.path):
            return self.path
        else:
            self.download()
            return self.path

    def get_authors_affiliations(self):
        return PaperExtractor(self.get_path(), self.title, self.authors_reference).get_authors_affiliations_locations()

    def fix_authors_names_from_reference(self):
        output = {}
        for author in self.authors_affiliations.keys():
            output[get_closest_from_list(author, self.authors_reference)] = self.authors_affiliations[author]
        self.authors_affiliations = output

        if len(self.authors_affiliations) != len(self.authors_reference):
            raise Exception("Authors number is inaccurate")
