import re
import json
from typing import Dict, List, Tuple

import fitz  # PyMuPDF
from PIL import Image
import  pdfquery

from rectangle import Rectangle


with open("data/postal_codes.json") as f:
    POSTAL_CODES_REGEX = json.load(f)#set([value for value in json.load(f).values()])


def substring_sieve(string_list):
    string_list.sort(key=lambda s: len(s), reverse=True)
    out = []
    for s in string_list:
        if not any([s in o for o in out]):
            out.append(s)
    return out


def get_postal_codes(line):
    matches = []
    for country, r in POSTAL_CODES_REGEX.items():
        if match := re.findall(r, line):
            matches += match

    matches = [m for m in matches if m != '' and not isinstance(m, tuple)]

    return substring_sieve(matches)


def get_location_names(raw_affiliations) -> Dict[str, List[str]]:
    postal_codes = get_postal_codes(raw_affiliations)
    for pc in postal_codes:
        raw_affiliations = raw_affiliations.replace(pc, "")

    affiliations = re.findall(r"[^\d⋆‡†]+", raw_affiliations)

    symbols: List[str] = re.findall(r"[\d⋆‡†]+", raw_affiliations)
    symbols = ['0'] if len(symbols) == 0 else symbols

    return {str(a.strip(", ")): b for a, b in zip(affiliations, symbols)}


def get_authors_affiliations(raw_authors) -> Dict[str, List[int]]:
    aff_authors = {}
    for sep in re.findall(r"[⋆‡†\d,]+", raw_authors):
        sep_index = raw_authors.find(sep)
        author = str(max(re.findall(r"[¨ˇŁł˙´a-zA-Z\s\.]+", raw_authors[:sep_index]), key=len)).strip()

        # NOTE Fixed noticed in kejriwal23b
        aff_authors[author] = re.findall(r"[⋆‡†\d]+", sep)
        aff_authors[author] = ['0'] if len(aff_authors[author]) == 0 else aff_authors[author]

        raw_authors = raw_authors[sep_index + len(sep):]

    return aff_authors


def is_element_before_affiliation(raw_line):
    sep_index = raw_line.find(re.findall(r"[⋆‡†\d,]+", raw_line)[0])
    return sep_index < 4


def get_affiliations(raw_line, sep="") -> Dict[str, List[str]]:
    # print(raw_line)
    raw_line = raw_line.replace("∗", "")

    # Removing potential postal codes from the extracted line
    postal_codes = get_postal_codes(raw_line)
    for pc in postal_codes:
        raw_line = raw_line.replace(pc, "")

    # print(raw_line)

    elements: List[str] = re.findall(rf"[^\d⋆‡†{sep}]+", raw_line)
    elements = [e.strip(' ,') for e in elements if e.strip(' ,') != '']
    # Make elements unique and keep order
    unique = []
    for e in elements:
        if e not in unique:
            unique.append(e)
    elements = unique

    symbols_groups = re.findall(r"[\d⋆‡†,\s]+", raw_line)
    symbols_groups = [a.strip(", ") for a in symbols_groups if a.strip(", ") != '']

    symbols: List[List[str]] = [re.findall(r"[\d⋆‡†]+", s) for s in symbols_groups if s != ","]

    # clean numbers
    clean = []
    for symbol in symbols:
        clean.append([])
        for s in symbol:
            if re.match(r"\d+", s) and re.match(r"\d+", s).group(0) != s:
                clean[len(clean) - 1].append(re.match(r"\d+", s).group(0))
            else:
                clean[len(clean) - 1].append(s)

    symbols = clean
    symbols = [['0'] for _ in range(len(elements))] if len(symbols) == 0 else symbols

    # print(elements)

    return {a: b for a, b in zip(elements, symbols)}


def contains_author(line, authors: List[str]) -> bool:
    for a in authors:
        if re.search(rf"\b{a}", line):
            return True
        for b in a.split(' '):
            # RISK this would be activated if someone's last name matches a company or lab name
            if re.search(rf"\b{b}", line) and b in line:
                return True
    return False


def is_abstract(line) -> bool:
    return "abstract" in line.lower()


def is_email(line) -> bool:
    return "@" in line


def is_title(line, title: str) -> bool:
    return line in title


def remove_inner_duplicates(duplicates: List[str]):
    i = 0
    while i < len(duplicates) - 1:
        if duplicates[i] in duplicates[i + 1]:
            duplicates.remove(duplicates[i])
        else:
            i += 1


def join_list(original: List[str]) -> str:
    output = original[0]
    for a, b in zip(original, original[1:]):
        # Joining a and b
        found = False
        for i in range(len(a) - min(len(a), len(b)), len(a)):
            if a[i:] == b[:len(a) - i]:
                output += b[len(a) - i:]
                found = True

        if not found:
            output += b

    return output


def split_on_major_gap(lines):
    gaps = [b - c for ((a, b), _), ((c, d), _) in zip(lines, lines[1:])]
    max_index = gaps.index(max(gaps))
    return [b for a, b in lines[:max_index + 1]], [b for a, b in lines[max_index + 1:]]


class PaperExtractor:

    def __init__(self, paper_path, paper_title: str, paper_authors):
        self.path = paper_path
        self.paper_title = paper_title
        self.paper_authors = paper_authors

        # Open the PDF file
        fitz_pdf = fitz.open(self.path)

        # Convert the first page to an image
        page = fitz_pdf.load_page(0)
        pixmap = page.get_pixmap(dpi=72)
        self.image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        self.width, self.height = self.image.size

        # Load pdf for query
        self.pdf = pdfquery.PDFQuery(self.path)
        self.pdf.load(0)

    def get_authors_affiliations_locations(self) -> Dict[str, List[str]]:
        lines: List[Tuple[List[int], str]] = [([0, 0], "")]
        for h in range(self.height, 0, -1):
            line = self.pdf.pq(f'LTTextLineHorizontal:overlaps_bbox("{0},{h},{self.width},{h}")').text()
            if line != "":
                if lines[-1][1] != line:
                    lines.append(([h, h], line))
                else:
                    lines[-1][0][1] = h

        # Removing first ghost element & conference title & paper title
        # Maybe remove lines matching title too much?
        lines = lines[3:]

        # for line in lines:
        #     print(line)

        y_low = y_high = 0

        interesting_info = []
        establishments = []
        authors_affiliations = []
        found_authors = False
        for nb, line in lines:
            if contains_author(line, self.paper_authors) and not is_abstract(line) and not is_email(line) and not is_title(line, self.paper_title):
                # print("AUTHOR", nb, line)
                authors_affiliations.append(line)
                interesting_info.append((nb, line))
                found_authors = True
                y_low = nb[0]
            elif (found_authors and not is_abstract(line)
                  and not is_email(line)):
                # print("STILL AUTHOR", nb, line)
                interesting_info.append((nb, line))
                establishments.append(line)
            elif is_abstract(line) or is_email(line):
                # print("A_O_E", nb, line)
                y_high = nb[1]
                break

        authors_affiliations, establishments = split_on_major_gap(interesting_info)

        print(authors_affiliations)
        remove_inner_duplicates(authors_affiliations)
        authors_affiliations = join_list(authors_affiliations)
        authors_affiliations = authors_affiliations.replace("and", "")
        authors_affiliations = get_affiliations(authors_affiliations, sep=",")
        print(authors_affiliations)

        print(establishments)
        remove_inner_duplicates(establishments)
        establishments = join_list(establishments)
        establishments = get_affiliations(establishments)
        print(establishments)

        output: Dict[str, List[str]] = {author: [] for author in authors_affiliations.keys()}

        for author, symbols in authors_affiliations.items():
            for auth_symbol in symbols:
                for location, loc_symbols in establishments.items():
                    if auth_symbol in loc_symbols:
                        output[author].append(location)


        rect = Rectangle(self.path, self.height - y_low, self.height - y_high)

        # print(0, self.height - y_low, self.width, self.height - y_high, y_low - y_high)
        # self.image = self.image.crop((0, self.height - y_low, self.width, self.height - y_high))
        # self.image.save("output_0.png")
        rect.export()

        return output


if __name__ == '__main__':
    import glob

    for path in glob.glob("data/papers/interspeech23/*.pdf"):
        print(path)
        PaperExtractor(path).get_authors_affiliations_locations()
        break
