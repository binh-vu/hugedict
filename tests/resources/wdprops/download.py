"""
Download the mapping from wikidata property ids to their labels.

Prerequisite:
    pip install web-table-extractor
"""


from pathlib import Path
from table_extractor.fetch_table import fetch_tables
from tqdm import tqdm

pages = [
    "https://www.wikidata.org/wiki/Wikidata:List_of_properties/human",
    "https://www.wikidata.org/wiki/Wikidata:List_of_properties/graph",
    "https://www.wikidata.org/wiki/Wikidata:List_of_properties/e-commerce",
]

outdir = Path(__file__).parent

for page in tqdm(pages):
    outfile = outdir / (page.rsplit("/", 1)[-1] + ".tsv")
    tables = fetch_tables(page)
    map = {}

    for table in tables:
        header = table.rows[0]
        if (
            all(c.is_header for c in header.cells)
            and header.cells[0].value.strip() == "Title"
            and header.cells[1].value.strip() == "ID"
        ):
            for row in table.rows[1:]:
                title = row.cells[0].value.strip()
                id = row.cells[1].value.strip()
                map[id] = title

    with open(outfile, "w") as f:
        for id, title in map.items():
            f.write(f"{id}\t{title}\n")
