import json
import re
from typing import Dict, List

import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import  pdfquery


def get_horizontal_gaps_median(image, width, height):
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

    print(gaps_sizes)

    gaps = gaps[2:len(gaps_sizes) - 2]
    gaps_sizes = gaps_sizes[2:len(gaps_sizes) - 2]

    try:
        thresh = 1.75 * np.mean(gaps_sizes)
    except:
        thresh = 20

    return list(filter(lambda a: a[1] - a[0] > thresh, gaps))


def get_header_segment(image):
    image_data = image.load()
    gaps = get_horizontal_gaps_median(image_data, *image.size)

    segments = []

    for gap_a, gap_b in zip(gaps[:-1], gaps[1:]):
        segments.append((gap_a[1], gap_b[0]))

    return segments


def get_location_names(raw_affiliations):
    affiliations = Email.remove(raw_affiliations)
    affiliations = re.sub(r"[a-z]+\.[a-z]+", "", affiliations)

    affiliations = re.findall(r"\D+", affiliations)
    affiliations = [re.sub(r"[,{}\s;]+$", "", aff) for aff in affiliations if
                    re.sub(r"[,{}\s]+$", "", aff) != ""]

    if len(affiliations) > 0:
        last_affiliation = re.findall(r"([\.\w]+[, ](| )+)", affiliations[-1])
        last_affiliation = " ".join([a for a, _ in last_affiliation])
        affiliations[len(affiliations) - 1] = last_affiliation

    return [a.strip() for a in affiliations]


def get_authors_affiliations(raw_authors) -> Dict[str, List[int]]:
    authors = raw_authors.split(", ")

    aff_authors = {}
    for author in authors:
        aut = re.findall(r"[a-zA-Z\s]+", author)
        if len(aut) > 0:
            aut = aut[0].strip()
        else:
            continue

        aff = [int(n) for n in re.findall(r"\d+", author)]
        aff = [0] if len(aff) == 0 else aff
        aff_authors[aut] = aff

    return aff_authors


class PaperExtractor:

    def __init__(self, paper_path, authors_reference: List[str]):
        self.path = paper_path

    def extract_lines_from_pdf(self):
        pdf = pdfquery.PDFQuery(paper)
        pdf.load(0)

        pdf_file = fitz.open(paper)

        # Convert the first page to an image
        page = pdf_file.load_page(0)
        pixmap = page.get_pixmap(dpi=72)
        img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        w, h = img.size

        # pdf.tree.write(f'paper.xml', pretty_print = True)
        # for i in range
        a, b, c, d = [70, 710, 529, 710]
        a, b, c, d = [0, 0, 596, 842]
        # x0, y0, x1, y1

        lines = []
        for a in range(h, 0, -1):
            line = pdf.pq(f'LTTextLineHorizontal:overlaps_bbox("{0},{a},{w},{a}")').text()
            if line != "" and (len(lines) == 0 or lines[-1] != line):
                lines.append(line)

        # print("\n".join(lines[:20]))

        affiliations = []
        found_authors = False
        for line in lines:
            if is_author_line(line):
                found_authors = True
            if found_authors and not is_author_line(line) and not is_abstract(line) and not is_email(line):
                affiliations.append(line)
            if is_abstract(line) or is_email(line):
                break

        # print(affiliations)

        i = 0
        while i < len(affiliations) - 1:
            if affiliations[i] in affiliations[i + 1]:
                affiliations.remove(affiliations[i])
            else:
                i += 1

        # print("\n".join(affiliations))

        output = affiliations[0]
        for a, b in zip(affiliations, affiliations[1:]):
            # Joining a and b
            found = False
            for i in range(len(a) - min(len(a), len(b)), len(a)):
                # print(len(a[i:]), len(b[:len(a) - i]))
                # print(a[i:], "\n", b[:len(a) - i])

                if a[i:] == b[:len(a) - i]:
                    output += b[len(a) - i:]
                    found = True
                    # print("->", a[i:], "\n->", b[:len(a) - i])
                    # print(output)
                    # print("Matched!")

            if not found:
                # print("here")
                output += b

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

        for key, (i, (a, b)) in zip(["authors", "locations"], enumerate(get_header_segment(image))):
            a, b, c, d = 0, (height - b - 1) / factor, width, (height - a + 1) / factor
            content[key] = pdf.pq(f'LTTextLineHorizontal:overlaps_bbox("{a},{b},{c},{d}")').text()

        content["locations"] = "" if "locations" not in content else content["locations"]

        return content["authors"], content["locations"]

    def get_authors_affiliations_locations(self):
        raw_authors, raw_locations = self.extract_paper_header()

        authors_affiliations = get_authors_affiliations(raw_authors)
        locations = get_location_names(raw_locations)

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
    import glob

    for path in glob.glob("data/papers/interspeech23/*.pdf"):
        print(path)
        PaperExtractor(path).get_authors_affiliations_locations()
        break
