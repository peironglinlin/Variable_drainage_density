import os
import gdal
import numpy as np
import pandas as pd
import sys
import glob
import geopandas as gpd
from shapely.geometry import Point,LineString,Polygon
import matplotlib.pyplot as plt
plt.switch_backend('agg')
# import pdb; pdb.set_trace()

def pixel2coord(x, y):
    xp = a * x + b * y + xoff + 0.5 * a  #(-+ 0.5 *a for pixel center)
    yp = d * x + e * y + yoff - 0.5 * a   #no need to invert y indices; bcuz geotiff data starts from top
    return (xp, yp)

f_riv = "raster/pfaf_02_strlnk.tif"
print('... reading '+f_riv+' ...')
f_dir = 'raster/'+f_riv[7:14]+'_dir.tif'
print('... reading '+f_dir+' ...')
ds1 = gdal.Open(f_riv)
ds2 = gdal.Open(f_dir)
ncols = ds1.RasterXSize
nrows = ds1.RasterYSize
driv = np.array(ds1.GetRasterBand(1).ReadAsArray())
ddir = np.array(ds2.GetRasterBand(1).ReadAsArray())
#geospatial info
xoff, a, b, yoff, d, e = ds1.GetGeoTransform()

#reclassify raster and store it in Pandas DataFrame
rivIndices = np.where(driv == 1)
ys = rivIndices[0]
xs = rivIndices[1]
nriv_grid = len(ys)
df = pd.DataFrame({'riv_ix':xs,'riv_iy':ys})  #pandas dataFrame to store indices with 
df['rivID'] = list(zip(df['riv_ix'],df['riv_iy']))
print(' --- river pixel number = '+str(nriv_grid)+' ---')

#calculate flowtoID
df['flowdir'] = ddir[ys,xs]
df['flowto_ix'] = xs
df['flowto_iy'] = ys
k = df['flowdir'].isin([1,2,128])  #to east
df['flowto_ix'].loc[k] = df['riv_ix'][k]+1
k = df['flowdir'].isin([8,16,32])  #to west
df['flowto_ix'].loc[k] = df['riv_ix'][k]-1
k = df['flowdir'].isin([32,64,128]) #to north
df['flowto_iy'].loc[k] = df['riv_iy'][k]-1
k = df['flowdir'].isin([2,4,8])  #to south
df['flowto_iy'].loc[k] = df['riv_iy'][k]+1 
#zip x/y into tuple coordinates
df['flowtoID'] = list(zip(df['flowto_ix'],df['flowto_iy']))
#mouth; depression; ocean
k = df['flowdir'].isin([0,-1,-9])  
df['flowtoID'].loc[k] = np.nan
df.drop(columns=['flowto_ix', 'flowto_iy'],inplace=True)

#find channel head
head = set(df['rivID'])-set(df['flowtoID'])  #they are rivers, but they have no flows in
nhead = len(head)
print(' --- channel head pixel number = '+str(nhead)+' ----')
#find junction
xtmp = df.groupby('flowtoID')['flowtoID'].count()
dfmerge = pd.DataFrame({'rivID':xtmp.index,'flowtoCount':xtmp.values})
df = df.merge(dfmerge,on='rivID',how='left')
df.fillna(-1,inplace=True)  #note: flowtoID river mouth, depression, ocean will become -1
# import pdb; pdb.set_trace()
df["flowtoCount"] = df["flowtoCount"].astype('int')
junction = df[df['flowtoCount']>1]['rivID'] #flowtoCount greater than 1
print(' --- junction pixel number = '+str(len(junction))+' ----')

#assign 1/0 to isHead and isJunction
df['node_flag']=0  #for any pixel in between
df['node_flag'].loc[df['rivID'].isin(head)] = -1  #for head
df['node_flag'].loc[df['rivID'].isin(junction)] = range(1,len(junction)+1)  #for junction
#set rivID as index for easier data access
df.set_index('rivID',inplace=True)

######### STEP 1#################################
# Assign comid for pixels between head and first junction
dfh = pd.DataFrame({'rivID':list(head),'comid':range(nhead),'order':1})
flowto = df.loc[dfh.rivID]
dfh['flowtoID'] = flowto['flowtoID'].values
k = (flowto['flowtoCount'].values == -1)  #flowtoCount for HEAD is -1
df1 = dfh[k].copy()
df1.order = df1.order+1
del df1['rivID']
df1.rename(columns = {'flowtoID':'rivID'},inplace=True)
while len(df1)>0:
    print(len(df1))
    flowto = df.loc[df1.rivID]
    df1['flowtoID'] = flowto['flowtoID'].values
    dfh = pd.concat([dfh, df1],sort=False)  #concatenate only for pixels before junctions

    k = (flowto['flowtoCount'].values == 1)
    df1 = df1[k].copy()
    df1.order = df1.order+1
    del df1['rivID']
    df1.rename(columns = {'flowtoID':'rivID'},inplace=True)

######## STEP 2#################################
# Assign comid for pixels after first junction
dfj = pd.DataFrame({'rivID':junction,'comid':range(nhead,nhead+len(junction)),'order':1})  #new array of comid for junctions
flowto = df.loc[dfj.rivID]
dfj['flowtoID'] = flowto['flowtoID'].values
k = (flowto['flowtoID'] != np.nan).values  #if next pixel after junction is not depression
df1 = dfj[k].copy()
df1.order = df1.order+1
del df1['rivID']
df1.rename(columns = {'flowtoID':'rivID'},inplace=True)
while len(df1)>0:
    print(len(df1))
#     import pdb; pdb.set_trace()
    atmp = df1.rivID == -1
    if (len(df1)==1) & (atmp.any()):  #river mouth to ocean
        break
    else:
        flowto = df.loc[df1.rivID]
        df1['flowtoID'] = flowto['flowtoID'].values
        dfj = pd.concat([dfj, df1],sort=False)

        k = (flowto['flowtoCount'].values == 1)
        df1 = df1[k].copy()
        df1.order = df1.order+1
        del df1['rivID']
        df1.rename(columns = {'flowtoID':'rivID'},inplace=True)

#######FINAL MERGE###############################
df_reach = pd.concat([dfh, dfj])#merge pixels with COMID after head and after junction
df.reset_index(inplace=True)
df = pd.merge(df,df_reach[['rivID','comid','order']],on='rivID',how='left')

#######create river geodataframe############
df.sort_values(by='order',inplace=True)  #sort data based on their orders along the flow direction
#import pdb; pdb.set_trace()
xss = a * df['riv_ix'].values + b * df['riv_iy'].values + xoff + 0.5 * a
yss = d * df['riv_ix'].values + e * df['riv_iy'].values + yoff - 0.5 * a
# tmp = pixel2coord(df['riv_ix'].values,df['riv_iy'].values)
# df['coords'] = list(zip(tmp[0],tmp[1]))
df['coords'] = list(zip(xss,yss))
rivgpd = df.groupby('comid')['coords'].apply(list).reset_index() #to retain column 'comid'
rivgpd['countPt'] = df.groupby('comid')['comid'].count()
rivgpd['fromnode'] = df.groupby('comid')['node_flag'].first().values
rivgpd['tonode'] = df.groupby('comid')['node_flag'].last().values

#only create line geometries for those with more than 1 point
rivgpd = rivgpd[rivgpd['countPt']>1]  
rivgpd['Coordinates'] = rivgpd['coords'].apply(lambda x: LineString(x))
rivgpd.drop(columns=['coords'],inplace=True)
rivgpd = gpd.GeoDataFrame(rivgpd,geometry='Coordinates')
print(' ---- there are '+str(len(rivgpd))+' reaches extracted ...')

fon = 'shapefile/test_'+f_riv[7:14]+'_flowline.shp'
print('... generating '+fon+' ...')
rivgpd.to_file(driver = 'ESRI Shapefile', filename = fon)
rivgpd.plot()
# plt.xlim(-90.,-89.)
# plt.ylim(33.5,34.5)
plt.savefig('test_rivgpd_02.jpg')
print('... plotting ...')
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        

