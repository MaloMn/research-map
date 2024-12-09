# Research map
Mapping labs with accepted papers to international conferences on speech and signal processing

## What is this?
This repository contains code to automatically extract authors affiliations from conference papers pdf files.
This data is then used to produce a map, available [here](http://malomn.github.io/map.html).

## How does it work?
### Architecture
- The `data` folder contains:
  - `data/conferences/{conference_name}`: link of the papers pdf files hosted online associated to an identifier
  - `data/papers/{conference_name}.json`: manually transcribed authors affiliations
 
Papers are manually transcribed when the automatic extraction fails.
Automatically recognized failures are stored in `output/{conference_name}/errors.json`.
A glance at the data can also help identifying

## How can you help?
1. Propose alternative methods to extract information from papers,
   - Methods should be as broad as possible, relying or not on external sources of informations ;
   - Methods should be **machine-learning free**, in order to keep the carbon footprint of this project as low as possible.
2. Manually review the data,
   - Correcting coordinates in the `locations.csv` file, or correcting authors affiliations.
3. Propose new ways to visualize the data.

## To-do

- [] Filter out positions (0, 0), and display paper without location them below the map in a table
- [] Add filters to the table to be able to see all papers
- [] Add papers from ICASSP
- [] Add papers from LREC
- [] Add papers from CALLING
