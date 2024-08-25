import requests
import os
import json

from tqdm import tqdm

from extractor import PaperExtractor


class Paper:

    FOLDER = "data/papers/"

    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.path = f"{Paper.FOLDER}{self.name}.pdf"

        # TODO Put these pdf in interspeech24 (should be name of links)

        self.authors, self.establishments = self.get_authors_affiliations()

    def download(self, folder="papers"):
        # Send a GET request to the URL
        response = requests.get(self.url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Save the PDF to the specified folder
            filepath = os.path.join(Paper.FOLDER, self.name)
            with open(filepath, "wb") as f:
                f.write(response.content)

        else:
            raise Exception(f"Failed to download: {self.url} (status-code={response.status_code})")

    def get_path(self):
        if os.path.exists(self.path):
            return self.path
        else:
            self.download()
            return self.path

    def get_authors_affiliations(self):
        return PaperExtractor(self.path).get_authors_affiliations_locations()


if __name__ == '__main__':
    with open("data/links.json") as f:
        links = json.load(f)

    for i, (paper_id, link) in tqdm(enumerate(links.items()), total=len(links)):
        print(paper_id)
        paper = Paper(paper_id, link)
        print(paper.authors, paper.establishments)

        if i == 20:
            break
