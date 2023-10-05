from cbers4asat import Cbers4aAPI
from cbers4asat.tools import rgbn_composite
from datetime import date, timedelta
from osgeo_utils import gdal2tiles
from osgeo.gdal import BuildVRT
from os import makedirs, remove, cpu_count
from shutil import rmtree
from os.path import exists
from glob import glob

api = Cbers4aAPI('teste@teste.com')

# Área de interesse. Pode ser: bouding box, path row ou polygon.
path_rows = [(176, 109), (176, 110)]

hoje = date.today()
semana_passada = hoje - timedelta(weeks=1, days=1)

if not exists('monitoramento'):
    makedirs('monitoramento')

if not exists('monitoramento/cenas'):
    makedirs('monitoramento/cenas')

if not exists('monitoramento/coloridas'):
    makedirs('monitoramento/coloridas')

if not exists('monitoramento/mosaico'):
    makedirs('monitoramento/mosaico')

if not exists('monitoramento/xyz'):
    makedirs('monitoramento/xyz')

for path_row in path_rows:
    produtos = api.query(location=path_row,
                        initial_date=semana_passada,
                        end_date=hoje,
                        cloud=100,
                        limit=100,
                         collections=["CBERS4_MUX_L4_DN", "CBERS4_MUX_L2_DN"])

    if len(produtos.get('features')):
        gdf = api.to_geodataframe(produtos, crs="EPSG:4326")

        cena = gdf[gdf.datetime == gdf.datetime.min()].head(1)

        data_imagem_mais_recente = cena.datetime.values[0].split('T')[0]
        id_imagem_mais_recente = cena.index.values[0]

        output_cenas = f'monitoramento/cenas/{data_imagem_mais_recente}-{id_imagem_mais_recente}'

        if not exists(output_cenas):
            makedirs(output_cenas)
        else:
            continue # Pular iteração, pois já existe

        api.download(
            products=cena,
            bands=['red', 'green', 'blue'],
            outdir=output_cenas,
            with_folder=False
        )

        path, row = path_row

        composition_filename = f'{id_imagem_mais_recente}_{data_imagem_mais_recente}_{path}_{row}.tif'
        rgb_outdir = 'monitoramento/coloridas/'

        rgbn_composite(
            red=glob(f'{output_cenas}/*_{path}_{row}_*_BAND7.tif')[0],
            green=glob(f'{output_cenas}/*_{path}_{row}_*_BAND6.tif')[0],
            blue=glob(f'{output_cenas}/*_{path}_{row}_*_BAND5.tif')[0],
            outdir=rgb_outdir,
            filename=composition_filename
        )

mosaico = BuildVRT(destName='monitoramento/mosaico/recente.vrt', srcDSOrSrcDSTab=glob('monitoramento/coloridas/*.tif'))
mosaico = None # Por algum motivo o arquivo só é criado se isso aqui existir, não me pergunte pq
gdal2tiles.main(['',
                 '-p', 'mercator',
                 '-z', '7-15',
                 '-w', 'none',
                 '-r', 'near',
                 '--processes', str(cpu_count()),
                 '--xyz',
                 '-q',
                 'monitoramento/mosaico/recente.vrt',
                 'monitoramento/xyz'
                 ])

remove('monitoramento/mosaico/recente.vrt')

for file in glob('monitoramento/cenas/*'):
    rmtree(file)

for file in glob('monitoramento/coloridas/*.tif'):
    remove(file)
