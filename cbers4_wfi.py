from cbers4asat import Cbers4aAPI
from rasterio import open as rio_open
from cbers4asat.tools import rgbn_composite
from datetime import date, timedelta
from osgeo_utils import gdal2tiles
from osgeo.gdal import BuildVRT
from os import makedirs, cpu_count
from shutil import rmtree
from os.path import exists
from glob import glob

# Preencher
BASE_OUTPUT_DIR = "monitoramento"
BASE_OUTPUT_TEMP = f"/tmp/monitoramento-cb4-wfi-{date.today()}"

OUTPUT_XYZ_TILES = "xyz"

api = Cbers4aAPI("teste@teste.com")
# ==================

# Área de interesse. Pode ser: bouding box, path row ou polygon.
path_rows = [(176, 111)]

hoje = date.today()
semana_passada = hoje - timedelta(weeks=1)

if not exists(BASE_OUTPUT_DIR):
    makedirs(BASE_OUTPUT_DIR)

if not exists(BASE_OUTPUT_TEMP):
    makedirs(BASE_OUTPUT_TEMP)

for path_row in path_rows:
    produtos = api.query(
        location=path_row,
        initial_date=semana_passada,
        end_date=hoje,
        cloud=100,
        limit=100,
        collections=["CBERS4_AWFI_L4_DN", "CBERS4_AWFI_L2_DN"],
    )

    if len(produtos.get("features")):
        gdf = api.to_geodataframe(produtos, crs="EPSG:4326")

        cena = gdf[gdf.datetime == gdf.datetime.min()].head(1)

        data_imagem_mais_recente = cena.datetime.values[0].split("T")[0]
        id_imagem_mais_recente = cena.index.values[0]

        output_scenes_download = f"{BASE_OUTPUT_DIR}/cenas/{data_imagem_mais_recente}-{id_imagem_mais_recente}"

        if not exists(output_scenes_download):
            makedirs(output_scenes_download)
        else:
            continue  # Pular iteração, pois já existe

        api.download(
            products=cena,
            bands=["red", "green", "blue"],
            outdir=output_scenes_download,
            with_folder=False,
        )

        path, row = path_row

        composition_filename = (
            f"{id_imagem_mais_recente}_{data_imagem_mais_recente}_{path}_{row}.tif"
        )

        rgb_composite_outdir = f"{BASE_OUTPUT_TEMP}/coloridas/"

        if not exists(rgb_composite_outdir):
            makedirs(rgb_composite_outdir)

        rgbn_composite(
            red=glob(f"{output_scenes_download}/*_{path}_{row}_*_BAND15.tif")[0],
            green=glob(f"{output_scenes_download}/*_{path}_{row}_*_BAND14.tif")[0],
            blue=glob(f"{output_scenes_download}/*_{path}_{row}_*_BAND13.tif")[0],
            outdir=rgb_composite_outdir,
            filename=composition_filename,
        )

if len(glob(f"{BASE_OUTPUT_TEMP}/coloridas/*.tif")):
    for file in glob(f"{BASE_OUTPUT_TEMP}/coloridas/*.tif"):
        raster = rio_open(file)

        meta = raster.meta.copy()
        meta.update(dtype="int8", nodata=0)

        matrix = raster.read()
        matrix = ((matrix - matrix.min()) / (matrix.max() + matrix.min())) * 255

        with rio_open(file, "w", **meta) as r:
            r.write(matrix)

        del meta
        del matrix
        raster.close()

    mosaico = BuildVRT(
        destName=f"{BASE_OUTPUT_TEMP}/recente.vrt",
        srcDSOrSrcDSTab=glob(f"{BASE_OUTPUT_TEMP}/coloridas/*.tif"),
    )

    mosaico = None  # Por algum motivo o arquivo só é criado se isso aqui existir, não me pergunte pq

    gdal2tiles.main(
        [
            "",
            "-p",
            "mercator",
            "-z",
            "7-15",
            "-w",
            "none",
            "-r",
            "near",
            "--processes",
            str(cpu_count()),
            "--xyz",
            "-q",
            f"{BASE_OUTPUT_TEMP}/recente.vrt",
            OUTPUT_XYZ_TILES,
        ]
    )

if exists(BASE_OUTPUT_TEMP):
    rmtree(BASE_OUTPUT_TEMP)
