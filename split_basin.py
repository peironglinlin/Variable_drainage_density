import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import cascaded_union
import os

#This script splits the global basins (in total: 57025) following the Pfafstetter rules until all basins are under 5000 km2
#Peirong Lin, October 2019

def trace_upstream_id(COMID,riv):
    #function to trace the entire network upstream of river with ID equaling COMID
    #riv: whole network shapefile as GeoDataFrame; COMID: ID of river needs tracing upstream    
    if COMID not in riv:
        return [COMID]
    else:
        list_up_id = [COMID]
        for i in riv[COMID]:
            list_up_id += trace_upstream_id(i,riv)
        return list_up_id
    
def trace_interbasin(list_main,list_trib,riv):
    idlist = list_main
    for trib_id in list_trib:
        idlist += trace_upstream_id(trib_id,riv)
    return idlist
        
def to_list_up_id(x):
    result = []
    for c in ['up1','up2','up3','up4']:
        if x[c]!=0:
            result += [x[c]]
    if len(result)==0:
        result = np.nan
    return result

def convert2dict_upid(df):
    df['up_list'] = df.apply(to_list_up_id,axis=1)
    df_tmp = df[['COMID','up_list']].dropna()
    df_dict = dict(zip(df_tmp.COMID,df_tmp.up_list))
    del df['up_list']
    return df_dict

def read_all_rivers():
    list_df = []
    column_wanted = ['COMID','NextDownID','uparea','up1','up2','up3','up4','geometry']
    path = '../../../MERIT/raster/cleaned/new_shapefiles/shapefile_props/level_01/'
    for pfaf in range(1,9):
        print('... read river network pfaf = %02d ...'%pfaf)
        fn = os.path.join(path,'pfaf_%02d_riv_3sMERIT_props.shp'%pfaf)
        
        df_tmp = gpd.read_file(fn)[column_wanted]
        list_df.append(df_tmp)
    return pd.concat(list_df)

def find_main_stream(df_basin):
    df_sort = df_basin.sort_values(by='uparea',ascending=False) #prepare for drop_duplicates
    df_sort = df_sort.drop_duplicates(subset=['NextDownID'],keep='first')
    return df_sort

def find_outlet_id(df_basin):
    #most downstream reach ID
    return df_basin['COMID'][df_basin.uparea==df_basin.uparea.max()].values[0]

def find_list_main_id(outlet_id,upID_dict):
    #find all main stem reach ID
    list_main_id = [outlet_id]  
    while outlet_id in upID_dict:
        outlet_id = upID_dict[outlet_id]
        list_main_id.append(outlet_id)
    return list_main_id

def mark_tributary_and_interbasins(df_basin,df_main,trib_to_trace,list_main_id,df_trib):
    df_basin_dict = convert2dict_upid(df_basin)
    #find four largest tributary basins
    codes = [2,4,6,8]
    df_basin['code'] = 0
    for i,trib_id in enumerate(trib_to_trace['COMID']):
        idlist = trace_upstream_id(trib_id,df_basin_dict)
        df_basin.loc[df_basin['COMID'].isin(idlist),'code'] = codes[i]
    
    codes = [9,7,5,3,1]
    newmain = df_main[df_main['NextDownID'].isin(trib_to_trace['NextDownID'])]
    newmain = newmain.sort_values(by='uparea',ascending=True).reset_index().drop(columns=['index'])
    indices = [np.where(list_main_id==newmain['COMID'][i])[0][0] for i in range(len(newmain))]
    for i in range(len(indices)+1):
        if i == 0:
            list_main = list_main_id[indices[i]:len(list_main_id)] #main
        elif i == len(indices):
            list_main = list_main_id[0:indices[i-1]]
        else:
            list_main = list_main_id[indices[i]:indices[i-1]]
        list_trib = df_trib[(df_trib['NextDownID'].isin(list_main)) & 
                         (~df_trib['COMID'].isin(trib_to_trace['COMID']))]['COMID'].values.tolist()
        idlist = trace_interbasin(list_main,list_trib,df_basin_dict)
        df_basin.loc[df_basin['COMID'].isin(idlist),'code'] = codes[i]                
    return df_basin['code'].values

def read_all_area():
    #read catchment area file
    df_area = pd.DataFrame({})
    path = '../../../MERIT/raster/cleaned/new_shapefiles/tables_v0.2/'
    for pfaf in range(1,9):
        fn = os.path.join(path,'area_catchment_pfaf_%02d.csv'%pfaf)
        df_area = df_area.append(pd.read_csv(fn)) 
    return df_area
   
def update_basid(df_sub_basin):
    #find main, tributary, outlet, and the four largest tributary for each subbasin
    df_all_main = find_main_stream(df_sub_basin) #finding possible main stems
    df_all_tributary = df_sub_basin[~df_sub_basin['COMID'].isin(df_all_main['COMID'])]
    upID_dict = dict(zip(df_all_main.NextDownID,df_all_main.COMID))
    
    outlet_id = find_outlet_id(df_sub_basin) #most downstream reach ID
    list_main_id = find_list_main_id(outlet_id,upID_dict) #find all main stem reach ID
    df_main = df_sub_basin[df_sub_basin['COMID'].isin(list_main_id)]
    df_trib = df_all_tributary[df_all_tributary['NextDownID'].isin(list_main_id)] #find all tributary reach ID
    df_trib = df_trib.sort_values(by='uparea',ascending=False).reset_index().drop(columns=['index'])
    trib_to_trace = df_trib[0:4]

    if len(list_main_id)<5:
        df_sub_basin['code'] = ''
    else:
        new_codes = mark_tributary_and_interbasins(df_sub_basin,df_main,trib_to_trace,list_main_id,df_trib)  
        df_sub_basin['code'] = new_codes
    df_sub_basin['basid'] = df_sub_basin['basid'].map(str)+df_sub_basin['code'].map(str)
    del df_sub_basin['code']
    return df_sub_basin
 
def split_basin(df_basin):
    df_basin['basin_area'] = df_basin.groupby('basid')['area'].transform('sum')
    all_area = df_basin.groupby('basid')['area'].sum()
    n_to_trace = (all_area>=5000).sum()

    if n_to_trace == 0:
        return [df_basin]
    else:
        list_df = []
        for i,idnow in enumerate(df_basin['basid'].unique()):
            df_sub_basin = df_basin[df_basin['basid']==idnow]
            # if all_area[idnow]<5000:
                # df_sub_basin['basid'] = df_sub_basin['basid'].map(str)+'0'
            if all_area[idnow]>=5000:
                df_sub_basin = update_basid(df_sub_basin)
                if len(df_sub_basin.basid.unique()) == 1:
                    list_df += [df_sub_basin]
                    continue

            list_df += split_basin(df_sub_basin)

    return list_df


if __name__=='__main__': 
    cat = gpd.read_file('cleaned_catc/pfaf_all_catc_area.shp')
    cat['basid'] = cat['basid'].astype('int32')
    cat = cat[cat['areasqkm']>=5000]
    to_trace = cat['basid'].unique()
    n_to_trace = len(to_trace)
    print('... remaining basins that need decoding: %s ...'%n_to_trace)

    rr = 0
    df_all_rivers = read_all_rivers()
    df_all_rivers = gpd.sjoin(df_all_rivers,cat,op='within',how='inner')

    #add area attribute and orig_id
    df_area = read_all_area()
    df_all_rivers = df_all_rivers.merge(df_area,on='COMID',how='inner')
    df_all_rivers['orig_id'] = df_all_rivers['basid']

    column_wanted = ['basid','COMID','orig_id','area','uparea','NextDownID','up1','up2','up3','up4']
    df_all_rivers = df_all_rivers[column_wanted]
    df_all_rivers.to_pickle('test_data.pkl')

    df_all_rivers = pd.read_pickle('test_data.pkl')
    # import pdb;pdb.set_trace()

    measurer = np.vectorize(len)

    for i,idnow in enumerate(to_trace[0:]):
        print('   ... decoding for %s ...'%idnow)  
        df_basin = df_all_rivers[df_all_rivers['basid']==idnow]

        #split basin for each catc > 5000 km2
        df_new_basin = pd.concat(split_basin(df_basin))
        max_len = measurer(df_new_basin['basid'].values.astype(str)).max(axis=0)

        # import pdb;pdb.set_trace()
        df_new_basin['basid'] = df_new_basin['basid'].astype(str).str.ljust(max_len, '0')
        fon = 'outputs/decoded_basid_%s.csv'%idnow
        print('   ... writing to %s ...'%fon)
        df_new_basin.to_csv(fon,index=False)   
    
    
        

