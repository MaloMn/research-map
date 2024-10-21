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


class Conference:

    PAPERS_DIR = "data/papers/"
    CONFERENCES_DIR = "data/conferences/"
    OUTPUT_DIR = "output/"

    def __init__(self, name):
        self.name = name
        self.papers_path = f"{Conference.PAPERS_DIR}{name}/"
        self.manual_path = f"{Conference.PAPERS_DIR}{name}.json"
        self.links_path = f"{Conference.CONFERENCES_DIR}{name}.json"
        self.accents_path = f"data/accents.json"

        Path(f"{Conference.OUTPUT_DIR}{name}/").mkdir(parents=True, exist_ok=True)
        self.output_path = f"{Conference.OUTPUT_DIR}{name}/general.json"
        self.errors_path = f"{Conference.OUTPUT_DIR}{name}/errors.json"

        with open(self.manual_path, "r") as f:
            self.manual = json.load(f)

        with open(self.links_path) as f:
            self.links = json.load(f)

        with open(self.accents_path) as f:
            self.accents = json.load(f)

        self.correct_output = {}
        self.errors = {}

    def analyse(self, *args):
        limit = len(self.links) if len(args) == 0 or isinstance(args[0], str) else args[0]
        links = list(self.links.items())[:limit]

        if len(args) > 0 and isinstance(args[0], str):
            links = [(a, self.links[a]) for a in args]

        for i, (paper_id, link) in (pbar := tqdm(enumerate(links), total=len(links))):
            pbar.set_description(f"paper_id={paper_id}")

            if paper_id in self.manual:
                self.correct_output[paper_id] = self.manual[paper_id]
                continue

            try:
                paper = Paper(self.name, paper_id, link)
            except Exception as e:
                # raise e
                k = str(e)
                if k in self.errors:
                    self.errors[k].append(paper_id)
                else:
                    self.errors[k] = [paper_id]
                continue

            self.correct_output[paper_id] = {}
            for author, establishments in paper.authors_affiliations.items():
                cleaned = []
                for esta in establishments:
                    for a, b in self.accents.items():
                        esta = esta.replace(a, b)
                    cleaned.append(esta)
                self.correct_output[paper_id][author] = cleaned

        return self

    def export(self):
        with open(self.output_path, 'w+') as f:
            json.dump(self.correct_output, f, indent=4)

        with open(self.errors_path, 'w+') as f:
            json.dump(self.errors, f, indent=4)


if __name__ == '__main__':
    conf = Conference("interspeech23")
    conf.analyse()
    conf.export()
    # print(conf.correct_output)
    # print(conf.errors)
