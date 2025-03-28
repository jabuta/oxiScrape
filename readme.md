# Obras por Impuestos Scraper

This repository contains a Python script to:

1. **Download** the main HTML of proyectos de Obras por Impuestos.
2. **Parse** the HTML to extract project UUIDs.
3. **Fetch** each project’s detail page using `requests`.
4. **Compile** all data into a final CSV with the exact format specified.

Script was developed by [Obras por Impuestos Oxi Consultores](https://www.obrasximpuestos.com/)

## Requirements

- Python 3.7+  
- [pip](https://pip.pypa.io/en/stable/) (or [conda](https://docs.conda.io/en/latest/))
- The following Python libraries:
  - `requests`
  - `beautifulsoup4`
  - `lxml`
  - `pandas`

Install them via:

```bash
pip install requests beautifulsoup4 lxml pandas
```

*(Or use your preferred environment manager, e.g. `conda install -c conda-forge requests beautifulsoup4 lxml pandas`).*

---

## Usage

1. **Download the main HTML file** (the page listing all projects) to your local machine:

   ```bash
   wget https://obrasporimpuestos.renovacionterritorio.gov.co/ObrasImpuestos \
        -O projects_main.html \
        --no-check-certificate
   ```
   
   This saves the landing page (or the page containing the main table) as `projects_main.html`.

2. **Place the `projects_main.html`** in the same directory as the Python script (for example, `final_script.py`).

3. **Run the Python script**:

   ```bash
   python final_script.py
   ```

   - The script will parse `projects_main.html` to get the project UUIDs.
   - It will automatically fetch each project’s detail page at:
     ```
     https://obrasporimpuestos.renovacionterritorio.gov.co/ObrasImpuestos/_DetalleProyecto?idProyecto=<UUID>
     ```
   - It will parse those detail pages to extract fields like BPIN, Cost, Beneficiaries, etc.
   - Finally, it merges everything into a **final CSV** (named `final_projects.csv` by default) with the following columns:

     ```
     Index,
     BPIN,
     Name,
     name Corr,
     Meta Title,
     SLUG,
     Objective,
     Objective Corrected,
     Cost,
     Beneficiaries,
     Viabilization Date,
     Sector,
     Sector Corr,
     Preinvestment Costs,
     Classification,
     Location Data,
     LOC TABLE,
     Deptos,
     Jsonld
     ```

4. **Open or import** `final_projects.csv` in your spreadsheet or data tool of choice.

---

## Troubleshooting

- If you see an error like `Could not find a tree builder with the features you requested: lxml`, install or reinstall `lxml`:

  ```bash
  pip install lxml
  ```

- If you encounter SSL issues, the script may skip verification. You can remove `verify=False` if you trust the server’s certificate or have the appropriate certificates installed.

- For large datasets, the script will fetch each detail page individually. If you notice performance issues or server rate limits, you may need to add throttling or store detail pages locally.

---

## License

[MIT](./LICENSE) (or your preferred open-source license.)