import requests
import os
import json
import glob
from tqdm import tqdm
import fitz
from PIL import Image


class Paper:

    def __init__(self, name, url):
        self.name = name
        self.url = url

    def download(self, folder="papers"):
        # Send a GET request to the URL
        response = requests.get(self.url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Extract the filename from the URL
            filename = self.url.split("/")[-1]

            # Save the PDF to the specified folder
            filepath = os.path.join(folder, filename)
            with open(filepath, "wb") as f:
                f.write(response.content)

        else:
            print(f"Failed to download: {self.url}, Status code: {response.status_code}")

    def get_affiliation(self):
        pdf_file = fitz.open(f"papers/{self.name}.pdf")

        # Convert the first page to an image
        page = pdf_file.load_page(0)
        pixmap = page.get_pixmap(dpi=72 * 4)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

        # Split the image horizontally based on white spaces
        def split_image_horizontally(image, threshold=10):
            width, height = image.size
            image_data = image.load()

            # List to store split images
            split_images = []

            similar_count = 0
            rows = []

            previous_value = True

            # Iterate over each row
            for row in range(height):
                # Check if the row is all white
                row_is_white = all(image_data[col, row] == (255, 255, 255) for col in range(width))

                if previous_value != row_is_white:
                    rows.append((similar_count, previous_value))
                    previous_value = row_is_white
                    similar_count = 1
                else:
                    similar_count += 1

            rows.append((similar_count, previous_value))

            for i, (n, is_white) in enumerate(rows):
                if is_white and n < threshold:
                    rows[i] = (n, False)

            # print(rows)

            # Aggregating similar boolean values
            transformed_array = []
            current_sum = 0
            current_bool = None

            for number, boolean in rows:
                if boolean == current_bool:
                    current_sum += number
                else:
                    if current_bool is not None:
                        transformed_array.append((current_sum, current_bool))
                    current_sum = number
                    current_bool = boolean

            # Append the last aggregated value
            if current_bool is not None:
                transformed_array.append((current_sum, current_bool))

            # print(transformed_array)

            start = 0
            for length, boolean in transformed_array:
                if not boolean:
                    split_image = image.crop((0, start, width, start + length))
                    split_images.append((start, start + length, split_image))

                start += length

            return split_images

        # Split the image
        split_images = split_image_horizontally(image, threshold=5 * 4)
        start = split_images[3][0]

        # split_images[3][2].save("big.png")

        split_images = split_image_horizontally(split_images[3][2], threshold=3 * 4)
        end = start + split_images[0][1]

        # print(start, end)

        # Save or display the split images
        split_images[0][2].save(f"affiliations/{self.name}.png")

        return split_images[0][2]


if __name__ == '__main__':
    # 1. Download papers
    with open("links.json") as f:
        links = json.load(f)

    for name, pdf in tqdm(links.items()):
        paper = Paper(name, pdf)
        paper.download()
        paper.get_affiliation()


