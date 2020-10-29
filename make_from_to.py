import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
import glob
import os

def convert_to_int(df):
    x = df['fromnode'].append(df['tonode'], ignore_index=True)

    dict_mapping = dict(zip(x.unique(),[i for i in range(len(x.unique()))]))
    df['fromnode'] = df['fromnode'].map(dict_mapping)
    df['tonode'] = df['tonode'].map(dict_mapping)
    return df

if __name__ == '__main__':
#     files = sorted(glob.glob('DATA_PUBLICATION/river_network_variable_Dd/*.shp'))
    files = sorted(glob.glob('DATA_PUBLICATION/river_network_constant_Dd/*.shp'))
    nf = len(files)
    # import pdb;pdb.set_trace()

    for file in files:
        #read line shapefile
        fin = file
        fon = 'NEW_DATA_PUBLICATION/river_network_constant_Dd/%s'%(fin.split('/')[2])
        
        if not os.path.isfile(fon):        
            ddd = gpd.read_file(fin)
            print('**** File '+fin+' *****')
            pfaf_id = fin.split('/')[2].split('_')[3].split('.')[0]
            print('   pfaf_id = %s'%pfaf_id)

            lines = ddd['geometry'][:]
            #start looping through all lines
            fromnode = []
            tonode = []
            print('... generating fromnode and tonode ...')
            for line in lines:
                #calculate actual length in km (multiple points)
                linecoords = line.coords[:]
                npt = len(linecoords)
                #calculate direct length in km (two points)
                point1 = Point(linecoords[npt-1])
                point2 = Point(linecoords[0])
                fromnode.append(str(point1.x)+','+str(point1.y))
                tonode.append(str(point2.x)+','+str(point2.y))
            ddd['fromnode'] = fromnode
            ddd['tonode'] = tonode

            #convert fromnode/tonode strings to integers
            df = convert_to_int(ddd)[['LINKNO','strmOrder','strmDrop','lengthkm','Slope','fromnode','tonode','geometry']]
            df = gpd.GeoDataFrame(df,geometry=df.geometry)

            print('... writing to %s ...'%fon)    
            df.to_file(fon)
