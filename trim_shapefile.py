import geopandas as gpd
import pandas as pd
import numpy as np
import glob
import os

basnos = [
          '11', '12', '13', '14', '15', '16', '17', '18',
          '21', '22', '23', '24', '25', '26', '27', '28', '29',
          '31', '32', '33', '34', '35', '36',
          '41', '42', '43', '44', '45', '46', '47', '48', '49',
          '51', '52', '53', '54', '55', '56', '57',
          '61', '62', '63', '64', '65', '66', '67',
           '74','75', '76', '77', '78',
          '81', '82', '83', '84', '85', '86'
         ]

def trim_shapefile(df):
    tot_length = sum(df.lengthkm)
    if df['ds'][0] is None:
        return df
    else:
        target = df['basin_area'][0]*df['ds'][0]  #km2 x km-1 = km
        if target < tot_length: #too dense with 1km2 threshold
            index = abs(df['cum_length'] - target).idxmin()
            if index+1>len(df):
                return df
            else:
                return df.iloc[0:index+1]
        else:
            return df

for pfaf in basnos:
    print('... PFAF = %s ...'%pfaf)
    files = sorted(glob.glob('shapefile_decoded/decoded_net_%s_*.shp'%pfaf))
    nf = len(files)

    df_list = []
    for i in range(nf):
        fin = files[i]
        print('   ... reading %s ...'%fin)
        #read decoded polygons
        df = gpd.read_file(fin)[['LINKNO','Length','strmOrder','strmDrop','Slope',
                                 'DSContArea','USContArea','basid','PFAF_ID','ds','basin_area','geometry']]
        df['lengthkm'] = df['Length']/1000
        df.sort_values(by='DSContArea',ascending=False,inplace=True)
        df['cum_length'] = df.lengthkm.cumsum()
        df_list.append(trim_shapefile(df))

    df_final = pd.concat(df_list)    
    fon = 'shapefile_trim/decoded_net_%s.shp'%(pfaf)
    print('      ... writing to %s ...'%fon)
    df_final.to_file(fon)
