import json
from pathlib import Path

from tqdm import tqdm

from paper import Paper

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

        Path(self.papers_path).mkdir(parents=True, exist_ok=True)

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
                        esta = esta.replace(a.upper(), b.upper())

                    cleaned.append(esta)
                self.correct_output[paper_id][author] = cleaned

            self.correct_output[paper_id] = {
                "url": paper.page_url,
                "title": paper.title,
                "authors": self.correct_output[paper_id]
            }

        return self

    def export(self):
        with open(self.output_path, 'w+') as f:
            json.dump(self.correct_output, f, indent=4)

        with open(self.errors_path, 'w+') as f:
            json.dump(self.errors, f, indent=4)

    def get_merged_affiliations(self):
        with open(self.output_path) as f:
            data = json.load(f)

        with open(self.manual_path) as f:
            manual = json.load(f)

        # adding manually transcribed papers
        for key, value in manual.items():
            data[key] = value

        return data


if __name__ == '__main__':
    conf = Conference("interspeech24")
    conf.analyse()
    conf.export()

    print(conf.correct_output)
    print(conf.errors)
