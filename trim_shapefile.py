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
          '61','62', '63', '64', '65', '66', '67',
          '71','72','73','74','75', '76', '77', '78',
          '81', '82', '83', '84', '85', '86'
         ]

def trim_shapefile(df):
    tot_length = sum(df.lengthkm)
    if df['dd'][0] is None:
        return df
    else:
        target = df['basin_area'][0]*df['dd'][0]  #km2 x km-1 = km
        if target < tot_length: #too dense with 1km2 threshold
            index = abs(df['cum_length'] - target).idxmin()
            if index+1>len(df):
                return df
            else:
                return df.iloc[0:index+1]
        else:
            return df

def list_files(pfaf):
    files = sorted(glob.glob('../data/shapefile_decoded/decoded_net_%s_*.shp'%pfaf))
    return files
        
for pfaf in basnos:
    print('... PFAF = %s ...'%pfaf)
    files = list_files(pfaf)
    nf = len(files)

    #read machine learning-derived Dd
    ddd = pd.read_csv('data/data_features_basid.csv')[['basid','dd']]

    df_list = []
    for i in range(nf):
        fin = files[i]
        print('   ... reading %s ...'%fin)
        #read decoded polygons
        df = gpd.read_file(fin)[['LINKNO','Length','strmOrder','strmDrop','Slope',
                                 'DSContArea','basid','PFAF_ID','basin_area','geometry']]
        df = df.merge(ddd,on='basid',how='left') #add newly estimated dd
        df['lengthkm'] = df['Length']/1000
        df.sort_values(by='DSContArea',ascending=False,inplace=True)
        df = df.reset_index().drop(columns=['index']) #important for finding the right index
        df['cum_length'] = df.lengthkm.cumsum()
        tmp = trim_shapefile(df)
        #update new dd
        tmp['dd'] = sum(tmp.lengthkm)/tmp['basin_area']
        df_list.append(tmp)

    df_final = pd.concat(df_list)  
    fon = 'shapefile_trim/decoded_net_%s.shp'%(pfaf)
    print('      ... writing to %s ...'%fon)
    df_final.to_file(fon)

