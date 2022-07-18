import os
import gdal
import numpy as np
import sys
import glob
import geopandas as gpd
from shapely.geometry import Point,Polygon

#list all files
files = glob.glob("dir/*_dir.tif")

#read continent shapefile
l = gpd.read_file('continents/hybas_global_lev02_v1c.shp')
print(l.columns)
print(l['PFAF_ID'].values)
print(l['UP_AREA'].values)
l=l[['PFAF_ID','geometry']]


def inPolygon(tile,poly):
    ds = gdal.Open(tile)
    width = ds.RasterXSize
    height = ds.RasterYSize
    gt = ds.GetGeoTransform()
    minx = gt[0]
    miny = gt[3] + width*gt[4] + height*gt[5] 
    maxx = gt[0] + width*gt[1] + height*gt[2]
    maxy = gt[3]
    polytile = Polygon([(minx,miny),(minx,maxy),(maxx,maxy),(maxx,miny),(minx,miny)])
    return polytile.intersects(poly)
    
def searchAllTiles(poly):
    tiles = []
    for tile in files:
        if inPolygon(tile,poly):
            tiles.append(tile)
    return tiles  #return a list of tiles in continent

for pfaf_id in l['PFAF_ID'].values:
    print('*******************************')
    print('  pfaf_id = '+str(pfaf_id))
    #len(list(l['PFAF_ID'].values).unique())
    poly = l[l['PFAF_ID']==pfaf_id]['geometry'].iloc[0]  #polygon of the current continent
    tiles = searchAllTiles(poly)

    #merge tiles using gdalbuiltvrt 
    myfile = ' '.join(tiles)
    print('... merging raster for '+str(pfaf_id)+' ...')
    os.system('gdalbuildvrt raster/pfaf_%02d'%pfaf_id+'_dir.vrt '+myfile)
    os.system('gdal_translate raster/pfaf_%02d'%pfaf_id+'_dir.vrt raster/pfaf_%02d'%pfaf_id+'_dir.tif')
    
    
    
    
    
    
