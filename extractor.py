import json
import re
from typing import Dict, List

import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import  pdfquery


class PaperExtractor:

    def __init__(self, paper_path):
        self.path = paper_path

    def get_horizontal_gaps_median(self, image, width, height):
        white_count = 0
        gaps_sizes = []
        gaps = []

        # Iterate over each row
        for row in range(height):
            # Check if the row is all white
            row_is_white = all(image[col, row] == (255, 255, 255) for col in range(width))

            if row_is_white:
                white_count += 1
            elif white_count > 0:
                gaps.append((row - white_count, row))
                gaps_sizes.append(white_count)
                white_count = 0

        if white_count > 0:
            gaps_sizes.append(white_count)

        gaps = gaps[2:len(gaps_sizes) - 2]
        gaps_sizes = gaps_sizes[2:len(gaps_sizes) - 2]

        try:
            thresh = 1.75 * np.mean(gaps_sizes)
        except:
            thresh = 20

        return list(filter(lambda a: a[1] - a[0] > thresh, gaps))

    def get_header_segment(self, image):
        image_data = image.load()
        gaps = self.get_horizontal_gaps_median(image_data, *image.size)

        segments = []

        for gap_a, gap_b in zip(gaps[:-1], gaps[1:]):
            segments.append((gap_a[1], gap_b[0]))

        return segments

    def extract_paper_header(self, factor=4):
        # Open the PDF file
        fitz_pdf = fitz.open(self.path)

        # Convert the first page to an image
        page = fitz_pdf.load_page(0)
        pixmap = page.get_pixmap(dpi=72 * factor)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        width, height = image.size

        pdf = pdfquery.PDFQuery(self.path)
        pdf.load(0)

        content = {}

        for key, (i, (a, b)) in zip(["authors", "locations"], enumerate(self.get_header_segment(image))):
            a, b, c, d = 0, (height - b - 1) / factor, width, (height - a + 1) / factor
            content[key] = pdf.pq(f'LTTextLineHorizontal:overlaps_bbox("{a},{b},{c},{d}")').text()

        print(content)
        return content["authors"], content["locations"]

    def get_location_names(self, raw_affiliations):
        affiliations = Email.remove(raw_affiliations)
        affiliations = re.sub(r"[a-z]+\.[a-z]+", "", affiliations)

        affiliations = re.findall(r"\D+", affiliations)
        affiliations = [re.sub(r"[,{}\s;]+$", "", aff) for aff in affiliations if
                        re.sub(r"[,{}\s]+$", "", aff) != ""]

        last_affiliation = re.findall(r"([\.\w]+[, ](| )+)", affiliations[-1])
        last_affiliation = " ".join([a for a, _ in last_affiliation])

        affiliations[len(affiliations) - 1] = last_affiliation

        return [a.strip() for a in affiliations]

    def get_authors_affiliations(self, raw_authors) -> Dict[str, List[int]]:
        authors = raw_authors.split(", ")

        aff_authors = {}
        for author in authors:
            aut = re.findall(r"[a-zA-Z\s]+", author)[0].strip()
            aff = [int(n) for n in re.findall(r"\d+", author)]
            aff = [0] if len(aff) == 0 else aff
            aff_authors[aut] = aff

        return aff_authors

    def get_authors_affiliations_locations(self):
        raw_authors, raw_locations = self.extract_paper_header()

        authors_affiliations = self.get_authors_affiliations(raw_authors)
        locations = self.get_location_names(raw_locations)

        return authors_affiliations, locations


class Email:

    REGEX = [
        r"[\w\._]+(\s+|)@[\w\.]+",
        r"{[a-z\_., ]+}@[a-z\.]+",
        r"@[\w\.]+"
    ]

    @staticmethod
    def remove(text: str):
        temp = text
        for pattern in Email.REGEX:
            temp = re.sub(pattern, "", temp)

        return temp


if __name__ == '__main__':
    # locations = [["Paper", "Name", "Latitude", "Longitude"]]


    # results = {}
    # for path in tqdm(glob.glob("papers/*.pdf")):
    #     results[path] = extract_from_paper(path)
    #
    # with open("results.json", "w+") as f:
    #     json.dump(results, f, indent=4)

    with open("output/results.json", "r") as f:
        results = json.load(f)




            # for a in affiliations:
            #     locations.append([paper, a, *get_location_coordinates(a, api_key)])

    # with open("locations.csv", "w+") as f:
    #     writer = csv.writer(f, delimiter=",")
    #     writer.writerows(locations)
