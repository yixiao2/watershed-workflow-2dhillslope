"""Perimeter-wide severity analysis and isolated artificial ATS forcing cases."""

import json
import os
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import h5py
import numpy as np
import pandas as pd
import xarray as xr

from config_utils import phase_dates, first_postfire_year, artificial_baseline_year
import postfire_utils as post

CLASSES = {1: "no-low", 2: "low", 3: "moderate", 4: "high"}
VEGETATION = {"Evergreen Forest": 1, "Shrub Scrub": 10}


def save_json(path, value):
    """Write standards-compliant JSON; missing statistics become null."""
    def clean(x):
        if isinstance(x, dict):
            return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple, np.ndarray)):
            return [clean(v) for v in x]
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (float, np.floating)):
            return float(x) if np.isfinite(x) else None
        if isinstance(x, np.bool_):
            return bool(x)
        return x
    Path(path).write_text(json.dumps(clean(value), indent=2, allow_nan=False) + "\n")


def calendar_index(values):
    # APPEEARS labels use Julian cftime metadata: preserve their stated dates.
    return pd.DatetimeIndex([pd.Timestamp(v.year, v.month, v.day) for v in values])


def noleap_dates(start, end):
    dates = pd.date_range(start, end)
    return dates[~((dates.month == 2) & (dates.day == 29))]


def edges(centers):
    centers = np.asarray(centers, float)
    post.require(len(centers) >= 2 and np.all(np.diff(centers) != 0), "Invalid spatial centers")
    return np.r_[centers[0] - (centers[1] - centers[0]) / 2,
                 (centers[:-1] + centers[1:]) / 2,
                 centers[-1] + (centers[-1] - centers[-2]) / 2]


def footprint(x0, x1, y0, y1, transformer):
    from shapely.geometry import Polygon
    # Densify angular grid edges before transforming into the equal-area CRS.
    q = np.linspace(0, 1, 9)
    x = np.r_[x0 + q * (x1-x0), np.full(9, x1), x1-q*(x1-x0), np.full(9, x0)]
    y = np.r_[np.full(9, y0), y0+q*(y1-y0), np.full(9, y1), y1-q*(y1-y0)]
    tx, ty = transformer.transform(x, y)
    return Polygon(zip(tx, ty))


def severity_areas(geometry, raster):
    """Exact polygon/30-m-cell intersection areas, excluding codes outside 1..4."""
    from rasterio.windows import from_bounds, Window
    from rasterio.features import geometry_mask
    from shapely.geometry import Polygon, mapping
    from shapely.prepared import prep
    window = from_bounds(*geometry.bounds, raster.transform)
    window = Window(np.floor(window.col_off), np.floor(window.row_off),
                    np.ceil(window.col_off + window.width) - np.floor(window.col_off),
                    np.ceil(window.row_off + window.height) - np.floor(window.row_off))
    try:
        window = window.intersection(Window(0, 0, raster.width, raster.height))
    except Exception:
        return np.zeros(4)
    data = raster.read(1, window=window)
    transform = raster.window_transform(window)
    touched = geometry_mask([mapping(geometry)], out_shape=data.shape,
                            transform=transform, invert=True, all_touched=True)
    prepared = prep(geometry)
    result = np.zeros(4)
    area = abs(transform.a * transform.e - transform.b * transform.d)
    for r, c in zip(*np.where(touched & np.isin(data, [1, 2, 3, 4]))):
        cell = Polygon([transform*(c,r), transform*(c+1,r),
                        transform*(c+1,r+1), transform*(c,r+1)])
        result[int(data[r, c])-1] += area if prepared.contains(cell) else geometry.intersection(cell).area
    return result


def classify_grid(lon, lat, perimeter_path, raster_path):
    import geopandas as gpd
    import rasterio
    from pyproj import Transformer
    from shapely.prepared import prep
    records = []
    xe, ye = edges(lon), edges(lat)
    with rasterio.open(raster_path) as src:
        perimeter = gpd.read_file(perimeter_path).to_crs(src.crs).geometry.unary_union
        prepared = prep(perimeter)
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        for r in range(len(lat)):
            for c in range(len(lon)):
                pixel = footprint(xe[c], xe[c+1], ye[r], ye[r+1], transformer)
                if not prepared.intersects(pixel):
                    continue
                clipped = perimeter.intersection(pixel)
                if clipped.area <= 0:
                    continue
                areas = severity_areas(clipped, src)
                if areas.sum() <= 0:
                    continue
                fractions = areas / areas.sum()
                tied = np.flatnonzero(np.isclose(areas, areas.max(), rtol=0, atol=1e-6))
                x, y = transformer.transform(float(lon[c]), float(lat[r]))
                records.append(dict(row=r, col=c, severity=int(tied[-1]+1),
                                    tie=len(tied)>1, x_m=x, y_m=y,
                                    pixel_area_m2=pixel.area, perimeter_area_m2=clipped.area,
                                    valid_area_m2=areas.sum(),
                                    mixed_fraction=1-fractions.max(),
                                    **{f"fraction_{k}": fractions[k-1] for k in CLASSES}))
    post.require(records, "No valid native pixels inside the fire perimeter")
    table = pd.DataFrame(records)
    width = max(2000.0, 2 * np.sqrt(table.pixel_area_m2.max()))
    table["block"] = [f"{int(x//width)}:{int(y//width)}" for x,y in zip(table.x_m, table.y_m)]
    table.attrs["block_width_m"] = width
    return table


def despike(frame, threshold=2.0, high_run_floor=6.0):
    """Same isolated-spike and short-high-run rules as get_MODIS-LAI."""
    out = frame.copy()
    count = 0
    for column in out:
        values = out[column].copy()
        previous, following = values.shift(1), values.shift(-1)
        neighbor = (previous + following) / 2
        mask = (values.notna() & previous.notna() & following.notna() &
                ((previous-following).abs() <= threshold) & ((values-neighbor).abs() > threshold))
        count += int(mask.sum())
        values.loc[mask] = neighbor.loc[mask]
        position = 0
        while position < len(values):
            if not pd.notna(values.iloc[position]) or values.iloc[position] < high_run_floor:
                position += 1
                continue
            end = position
            while end+1 < len(values) and pd.notna(values.iloc[end+1]) and values.iloc[end+1] >= high_run_floor:
                end += 1
            if position > 0 and end+1 < len(values) and end-position+1 <= 2:
                left, right = values.iloc[position-1], values.iloc[end+1]
                if pd.notna(left) and pd.notna(right) and (values.iloc[position:end+1] > max(left,right)+threshold).all():
                    for j in range(position,end+1):
                        values.iloc[j] = left+(right-left)*(j-position+1)/(end-position+2)
                        count += 1
            position = end+1
        out[column] = values
    return out, count


def bootstrap_medians(values, blocks, replicates=2000, seed=42):
    """Resample whole spatial blocks, retaining each block's member pixels."""
    values = np.asarray(values)
    if values.ndim == 1:
        values = values[:,None]
    groups = [np.flatnonzero(np.asarray(blocks)==b) for b in sorted(set(blocks))]
    if len(groups) < 5:
        return None
    rng = np.random.default_rng(seed)
    result = np.empty((replicates, values.shape[1]))
    for i in range(replicates):
        ids = np.concatenate([groups[j] for j in rng.integers(len(groups), size=len(groups))])
        result[i] = np.nanmedian(values[ids], axis=0)
    return result


def response_tables(response, numerator, denominator, spatial, variable, output, response_window):
    """Recovery diagnostics, fixed first-year seasonal ratios, and low-case evidence."""
    import warnings
    first_start, first_end = map(pd.Timestamp, response_window)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        monthly = response.resample("MS").median()
        first = response.loc[first_start:first_end]
        # Group actual first-year dates, so August does not pool later recovery.
        seasonal = first.groupby(first.index.month).median().reindex(range(1,13))
        tables = [("recovery", monthly), ("seasonal", seasonal)]
        results = {}
        for kind, frame in tables:
            values, boot = {}, {}
            for code in CLASSES:
                ids = spatial.index[spatial.severity == code].to_numpy()
                values[code] = frame[ids].median(axis=1).to_numpy() if len(ids) else np.full(len(frame), np.nan)
                boot[code] = bootstrap_medians(frame[ids].to_numpy().T, spatial.loc[ids,"block"].to_numpy(), seed=42+code) if len(ids) else None
            rows = []
            for code in CLASSES:
                ratio = np.ones(len(frame)) if code == 1 else values[code]/values[1]
                interval = None
                if boot[code] is not None and boot[1] is not None:
                    samples = boot[code]/boot[1] if code != 1 else np.ones_like(boot[1])
                    interval = np.nanquantile(samples,[.025,.975],axis=0)
                ids = spatial.index[spatial.severity == code].to_numpy()
                for j, date in enumerate(frame.index):
                    nvalid = int(frame.loc[date,ids].notna().sum()) if len(ids) else 0
                    rows.append(dict(variable=variable, severity=code, category=CLASSES[code],
                                     period=str(date.date()) if kind=="recovery" else int(date),
                                     response=values[code][j], ratio=ratio[j], valid_units=nvalid,
                                     total_units=len(ids), blocks=spatial.loc[ids,"block"].nunique(),
                                     ci_low=interval[0,j] if interval is not None else np.nan,
                                     ci_high=interval[1,j] if interval is not None else np.nan))
            results[kind] = pd.DataFrame(rows)
            results[kind].to_csv(output/f"{variable.replace(' ','_')}_{kind}.csv",index=False)

        # Integrated first-year response per independent pixel/cell, with matched support.
        dates = numerator.loc[first_start:first_end].index
        if variable != "DOC":
            dates = dates[np.isin(dates.month,range(5,10))]
        num, den = numerator.loc[dates], denominator.loc[dates]
        usable = response.loc[dates].notna()
        integrated = num.where(usable).sum(min_count=1)/den.where(usable).sum(min_count=1)
        metrics = {}
        for code in [1,2]:
            ids = spatial.index[(spatial.severity==code) & spatial.index.isin(integrated.index[integrated.notna()])]
            metrics[code] = dict(value=float(integrated[ids].median()), blocks=spatial.loc[ids,"block"].nunique(),
                                 boot=bootstrap_medians(integrated[ids],spatial.loc[ids,"block"],seed=42+code) if len(ids) else None)
        ratio = float(np.divide(metrics[2]["value"],metrics[1]["value"]))
        ci = [np.nan,np.nan]
        if metrics[1]["boot"] is not None and metrics[2]["boot"] is not None:
            ci = np.nanquantile(metrics[2]["boot"]/metrics[1]["boot"],[.025,.975]).tolist()
        evidence = dict(variable=variable, integrated_ratio=ratio, ci95=ci,
                        no_low_blocks=metrics[1]["blocks"], low_blocks=metrics[2]["blocks"],
                        significant=bool(np.isfinite(ratio) and abs(ratio-1)>=.1 and
                                         (ci[1]<1 or ci[0]>1)),
                        uncertainty_available=bool(np.isfinite(ci).all()))
        results["low_evidence"] = evidence
        means = numerator.resample("MS").mean()
        class_means = pd.DataFrame({CLASSES[k]:means[spatial.index[spatial.severity==k]].mean(axis=1) for k in CLASSES})
        class_means.to_csv(output/f"{variable.replace(' ','_')}_class_values.csv")
        results["class_values"] = class_means
        reference_means = denominator.resample("MS").mean()
        results["reference_values"] = pd.DataFrame({CLASSES[k]:reference_means[spatial.index[spatial.severity==k]].mean(axis=1) for k in CLASSES})
        results["reference_values"].to_csv(output/f"{variable.replace(' ','_')}_reference_values.csv")
        return results


def analyze_lai(lai_path, landcover_path, perimeter_path, raster_path, output, end_date, config):
    output = Path(output); output.mkdir(parents=True,exist_ok=True)
    first_start, first_end = first_postfire_year(config)
    reference_start = f"{first_start.year - 3}-01-01"
    reference_end = f"{first_start.year - 1}-12-31"
    landcover_year = first_start.year - 1
    with xr.open_dataset(lai_path) as d:
        spatial = classify_grid(d.lon.values,d.lat.values,perimeter_path,raster_path)
        times = calendar_index(d.time.values)
        # Include neighboring observations for interpolation and despiking.
        selected = np.flatnonzero((times >= pd.Timestamp(reference_start) - pd.Timedelta(days=31)) & (times <= pd.Timestamp(end_date)+pd.Timedelta(days=15)))
        raw = d.Lai_500m.isel(time=selected,lat=xr.DataArray(spatial.row.values,dims="pixel"),
                                lon=xr.DataArray(spatial.col.values,dims="pixel")).values
        native = pd.DataFrame(raw,index=times[selected],columns=spatial.index)
    with xr.open_dataset(landcover_path) as d:
        t = np.flatnonzero(calendar_index(d.time.values).year==landcover_year)
        post.require(len(t)==1,f"Missing {landcover_year} prefire land cover")
        spatial["modis_landcover"] = d.LC_Type1.isel(time=int(t[0]),
            lat=xr.DataArray(spatial.row.values,dims="pixel"),
            lon=xr.DataArray(spatial.col.values,dims="pixel")).values
    native = native.where((native >= 0)&(native < 10))
    native, replaced = despike(native)
    daily = native.reindex(native.index.union(pd.date_range(reference_start,end_date))).sort_index()
    daily = daily.interpolate(method="time",limit_area="inside").loc[reference_start:end_date]
    daily = daily[~((daily.index.month==2)&(daily.index.day==29))]
    cycle = daily.loc[reference_start:reference_end].groupby(daily.loc[reference_start:reference_end].index.strftime("%m-%d")).mean()
    after = daily.loc[pd.Timestamp(first_start):end_date]
    reference = pd.DataFrame(cycle.loc[after.index.strftime("%m-%d")].values,index=after.index,columns=after.columns)
    valid = reference >= .2
    raw_ratio = after/reference.where(valid)
    clipped = int(((raw_ratio<.05)|(raw_ratio>2)).sum().sum())
    ratio = raw_ratio.clip(.05,2)
    results = {}
    for vegetation, code in VEGETATION.items():
        ids = spatial.index[spatial.modis_landcover==code]
        results[vegetation] = response_tables(ratio[ids],after[ids],reference[ids],spatial.loc[ids],vegetation,output,(first_start,first_end))
        # Only months that really are dormant may receive a factor-1 fallback.
        dormant = reference[ids].groupby(reference.index.month).median().reindex(range(1,13))
        results[vegetation]["dormant"] = {s:[int(m) for m in dormant.index
              if len(spatial.index[(spatial.modis_landcover==code)&(spatial.severity==s)]) and
              dormant.loc[m,spatial.index[(spatial.modis_landcover==code)&(spatial.severity==s)]].median()<.2]
              for s in CLASSES}
    spatial.to_csv(output/"MODIS_native_pixels.csv",index_label="unit")
    save_json(output/"MODIS_QC.json",dict(despike_replacements=replaced,clipped_responses=clipped,
               excluded_responses=int(ratio.isna().sum().sum()),
               block_width_m=spatial.attrs["block_width_m"],landcover_year=landcover_year,
               crosswalk=VEGETATION,source_sha256={str(p):post.digest(p) for p in [lai_path,landcover_path]},
               native_counts=spatial.groupby(["modis_landcover","severity"]).size().to_dict()))
    return spatial,results


def paired_elm_files(root,run):
    directory = Path(root)/f"ELM_MOSART_CONUS.{run}"/"run"
    prefix = f"ELM_MOSART_CONUS.{run}.elm.h0."
    files = {}
    for path in directory.glob(prefix+"*.nc"):
        text = path.name[len(prefix):len(prefix)+10]
        try:
            date = pd.Timestamp(text)
        except ValueError:
            continue
        files[date] = path
    return files


def analyze_doc(config, perimeter_path, raster_path, soil_thickness, output, end_date, settings):
    import netCDF4
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    first_start, first_end = first_postfire_year(config)
    fire_run, nofire_run = settings["fire_elm_run"], settings["nofire_elm_run"]
    fire,nofire = paired_elm_files(settings["elm_root"],fire_run),paired_elm_files(settings["elm_root"],nofire_run)
    dates = noleap_dates(first_start,end_date)
    available = dates[dates.isin(fire)&dates.isin(nofire)]
    post.require(len(available)>0,"No paired fire/no-fire ELM samples")
    with xr.open_dataset(fire[available[0]]) as d:
        lon = (d.lon.values+180)%360-180
        lat = d.lat.values
    spatial=classify_grid(lon,lat,perimeter_path,raster_path)
    num,den = np.empty((len(available),len(spatial))),np.empty((len(available),len(spatial)))
    manifest=[]
    for i,date in enumerate(available):
        for files,target in [(fire,num),(nofire,den)]:
            path=files[date]
            # Read only HR/time/coordinates; decoding hundreds of unrelated ELM
            # variables with xarray for every daily file is unnecessarily costly.
            with netCDF4.Dataset(path) as d:
                post.require(len(d.dimensions["time"])==1,"Paired ELM analysis expects the documented daily files")
                time=d.variables['time']
                stamp=netCDF4.num2date(time[:],time.units,calendar=getattr(time,'calendar','standard'))
                post.require(calendar_index(stamp)[0]==date,"ELM filename/time mismatch")
                post.require(np.allclose((d.variables['lon'][:]+180)%360-180,lon) and
                             np.allclose(d.variables['lat'][:],lat),"Paired ELM grids differ")
                hr=d.variables['HR']
                post.require(hr.dimensions==('time','lat','lon'),"Unexpected HR dimensions")
                values=np.ma.filled(hr[0,:,:],np.nan)
                target[i]=values[spatial.row.values,spatial.col.values]*.01/soil_thickness/12
            stat=path.stat()
            manifest.append(dict(path=str(path),bytes=stat.st_size,mtime_ns=stat.st_mtime_ns))
        if i%100==0:print(f"Paired ELM: {i+1}/{len(available)} days",flush=True)
    num,den=pd.DataFrame(num,index=available,columns=spatial.index),pd.DataFrame(den,index=available,columns=spatial.index)
    np.savez_compressed(output/'ELM_paired_native_DOC.npz',dates=available.to_numpy(),
                        numerator=num.to_numpy(),denominator=den.to_numpy(),units=spatial.index.to_numpy())
    post.require(np.isfinite(num.values).all() and np.isfinite(den.values).all() and
                 (num.values>=0).all() and (den.values>=0).all(),"Invalid paired HR values")
    ratio=pd.DataFrame(np.nan,index=available,columns=spatial.index)
    thresholds={}
    for code in CLASSES:
        ids=spatial.index[spatial.severity==code]
        positive=den[ids].values[den[ids].values>0]
        threshold=float(np.median(positive)*1e-6) if len(positive) else np.nan
        thresholds[code]=threshold
        ratio[ids]=num[ids]/den[ids].where(den[ids]>threshold)
    clipped=int(((ratio<.05)|(ratio>2)).sum().sum())
    result=response_tables(ratio.clip(.05,2),num,den,spatial,"DOC",output,(first_start,first_end))
    spatial.to_csv(output/"ELM_native_cells.csv",index_label="unit")
    save_json(output/"ELM_QC.json",dict(fire_run=fire_run,no_fire_run=nofire_run,
              missing_dates=[str(d.date()) for d in dates if d not in available],
              near_zero_thresholds=thresholds,clipped_responses=clipped,
              excluded_responses=int(ratio.isna().sum().sum()),block_width_m=spatial.attrs["block_width_m"],
              soil_thickness_m=soil_thickness,f_DOM=.01,carbon_g_mol=12,
              native_counts=spatial.groupby("severity").size().to_dict()))
    save_json(output/"ELM_source_manifest.json",manifest)
    return spatial,result


def plot_analysis(lai,doc,output):
    import matplotlib.pyplot as plt
    results={**lai,"DOC":doc}
    for variable,result in results.items():
        fig,axes=plt.subplots(3,1,figsize=(11,10))
        colors=['tab:blue','tab:orange','tab:green','tab:red']
        result["class_values"].plot(ax=axes[0],color=colors);axes[0].set_ylabel("molC m$^{-3}$ s$^{-1}$" if variable=="DOC" else "LAI")
        result["reference_values"].plot(ax=axes[0],color=colors,linestyle="--",alpha=.6,legend=False)
        axes[0].set_title("Class means: fire response (solid), prefire seasonal / no-fire reference (dashed)")
        for code in CLASSES:
            recovery=result["recovery"].query("severity == @code")
            dates=pd.to_datetime(recovery.period)
            axes[1].plot(dates,recovery.ratio,label=CLASSES[code])
            axes[1].fill_between(dates,recovery.ci_low.to_numpy(float),recovery.ci_high.to_numpy(float),alpha=.15)
            seasonal=result["seasonal"].query("severity == @code")
            axes[2].plot(seasonal.period,seasonal.ratio,marker="o",label=CLASSES[code])
        axes[1].set_ylabel("Normalized monthly response (recovery)")
        axes[2].set_ylabel("Repeated seasonal multiplier");axes[2].set_xlabel("Calendar month")
        for ax in axes[1:]:ax.axhline(1,color="gray",linestyle="--");ax.legend();ax.grid(alpha=.2)
        fig.suptitle(variable+": fire-perimeter analysis; independent native spatial units")
        fig.tight_layout();fig.savefig(Path(output)/(variable.replace(" ","_")+"_analysis.png"),dpi=160)
        plt.show()


def plot_spatial_support(modis,elm,perimeter_path,raster_path,output):
    import geopandas as gpd
    import rasterio
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap,BoundaryNorm
    with rasterio.open(raster_path) as src:
        boundary=gpd.read_file(perimeter_path).to_crs(src.crs)
    fig,axes=plt.subplots(1,2,figsize=(14,6),sharex=True,sharey=True)
    cmap=ListedColormap(['darkgreen','aquamarine','gold','red'])
    norm=BoundaryNorm([.5,1.5,2.5,3.5,4.5],4)
    for ax,table,name in zip(axes,[modis,elm],['MODIS pixels','ELM cells']):
        boundary.boundary.plot(ax=ax,color='black',linewidth=1)
        points=ax.scatter(table.x_m,table.y_m,c=table.severity,cmap=cmap,norm=norm,s=8)
        ax.set_title(f'{name}: {len(table)} independent native units intersecting perimeter')
        ax.set_aspect('equal');ax.set_xlabel('Easting [m]');ax.set_ylabel('Northing [m]')
    bar=fig.colorbar(points,ax=list(axes),ticks=[1,2,3,4],shrink=.7)
    bar.ax.set_yticklabels(list(CLASSES.values()))
    fig.savefig(Path(output)/'native_spatial_support.png',dpi=160,bbox_inches='tight');plt.show()


def select_patterns(lai,doc,output):
    """Keep unavailable patterns unavailable; A0 requires no class estimate."""
    patterns={"A0":{v:np.ones(12) for v in [*VEGETATION,"DOC"]}}
    evidence=[r["low_evidence"] for r in [*lai.values(),doc]]
    include_low=any(e["significant"] for e in evidence)
    rejected={};inversions=[]
    for case,code in [("A1",2),("A2",3),("A3",4)]:
        if case=="A1" and not include_low:
            rejected[case]="Low/no-low effect did not meet effect-size and spatial-uncertainty criterion"
            continue
        pattern={};problems=[]
        for variable,result in {**lai,"DOC":doc}.items():
            rows=result["seasonal"].query("severity == @code").sort_values("period")
            values=rows.ratio.to_numpy(float)
            missing=~np.isfinite(values)
            dormant=set(result.get("dormant",{}).get(code,[])) & set(result.get("dormant",{}).get(1,[]))
            for month in dormant:
                if missing[month-1]:values[month-1]=1
            if len(values)!=12 or not np.isfinite(values).all() or np.any(values<=0):
                problems.append(variable+": missing or invalid seasonal support")
            pattern[variable]=values
        if problems:rejected[case]=problems
        else:patterns[case]=pattern
    for variable,result in {**lai,"DOC":doc}.items():
        pivot=result["seasonal"].pivot(index="period",columns="severity",values="ratio")
        for month,row in pivot.iterrows():
            if np.isfinite(row[[2,3,4]]).all() and not row[4]<=row[3]<=row[2]:
                inversions.append(dict(variable=variable,month=int(month),ratios=row.to_dict()))
    save_json(Path(output)/"case_selection.json",dict(low_evidence=evidence,rejected=rejected,
              severity_order_inversions=inversions,patterns=patterns,bootstrap_replicates=2000,seed=42))
    return patterns,rejected


def annual_multiplier(months,dates):
    post.require(np.shape(months)==(12,) and np.isfinite(months).all() and (np.asarray(months)>0).all(),"Invalid monthly multipliers")
    reference=pd.date_range("2001-01-01","2001-12-31")
    mids=np.array([((pd.Timestamp(2001,m,1)+pd.offsets.MonthEnd(0)).day-1)/2+
                   (pd.Timestamp(2001,m,1)-reference[0]).days for m in range(1,13)])
    # Daily sample at midnight; interpolate periodic monthly midpoint values.
    position=np.array([(pd.Timestamp(2001,d.month,d.day)-reference[0]).days for d in dates])
    return np.interp(position,np.r_[mids[-1]-365,mids,mids[0]+365],np.r_[months[-1],months,months[0]])


def canonical_dates(config):
    pre=pd.DatetimeIndex(phase_dates(config,"prefire_transient"))
    after=pd.DatetimeIndex(phase_dates(config,"postfire_transient"))
    offset=config["spinup"]["cyclic_years"]*365
    return pre,after,offset


def template_indices(config):
    pre,after,offset=canonical_dates(config)
    timeline=pre.append(after)
    baseline_year=artificial_baseline_year(config)
    year=noleap_dates(f"{baseline_year}-01-01",f"{baseline_year}-12-31")
    lookup={d:i+offset for i,d in enumerate(timeline)}
    post.require(all(d in lookup for d in year),f"Canonical forcing lacks complete observed {baseline_year}")
    year_indices=np.array([lookup[d] for d in year])
    indices=np.array([lookup[pd.Timestamp(baseline_year,d.month,d.day)] for d in after])
    return year_indices,indices


def write_case_forcing(target,config,report,pattern):
    """Copy canonical LAI/DOC, retain prefix, and replace the postfire tail."""
    folder=Path(target)/"forcing";folder.mkdir(exist_ok=True)
    start,end=report["start_day"],report["end_day"]
    _,after,_=canonical_dates(config)
    _,ids=template_indices(config)
    mapping={};checks={}
    candidates=[p for p in report["forcing_files"] if "MODIS_LAI" in p or "DOC_source" in p or "CNbc_conc" in p]
    for original in candidates:
        original=Path(original);out=folder/original.name
        shutil.copy2(original,out)
        with h5py.File(original) as source,h5py.File(out,"r+") as dest:
            if "MODIS_LAI" in original.name:
                for vegetation in VEGETATION:
                    key=f"NLCD {vegetation} LAI [-]"
                    values=source[key][:]
                    dest[key][start:end]=values[ids]*annual_multiplier(pattern[vegetation],after)
                    post.require(np.array_equal(dest[key][:start],values[:start]),"LAI prefix changed")
            elif "DOC_source" in original.name:
                scale=annual_multiplier(pattern["DOC"],after)
                group=dest[post.DOC_KEY]
                for j,index in enumerate(ids):
                    total=source[post.DOC_KEY][str(index)][:]*scale[j]
                    group[str(start+j)][:]=total
                    if "lambda10" in original.name:
                        for species,carbon in zip(post.SPECIES,post.CARBON):
                            dest[f"DOC production {species} [mol m^-3 s^-1]"][str(start+j)][:]=total/10/carbon
                for key in source:
                    if isinstance(source[key],h5py.Group):
                        for i in range(start):
                            post.require(np.array_equal(dest[key][str(i)][:],source[key][str(i)][:]),"DOC prefix changed")
                    else:post.require(np.array_equal(source[key][:],dest[key][:]),"DOC coordinates/clock changed")
            else:
                scale=annual_multiplier(pattern["DOC"],after)
                for key in source:
                    if key.startswith("DOC "):
                        values=source[key][:]
                        dest[key][start:end]=values[ids]*scale
                if "lambda10" in original.name:
                    total=dest[post.CN_KEY][start:end]
                    for species,carbon in zip(post.SPECIES,post.CARBON):
                        dest[f"{species} mol water basis [molS molH^-1]"][start:end]=total/10/carbon
                for key in source:
                    post.require(np.array_equal(source[key][:start],dest[key][:start]),"Boundary prefix changed")
                    if not key.startswith(("DOC ",*post.SPECIES)):
                        post.require(np.array_equal(source[key][:],dest[key][:]),"Non-DOC boundary changed")
        post.finite_hdf(out,end)
        mapping[str(original.resolve())]=str(out.resolve())
        checks[out.name]=dict(source_sha256=post.digest(original),output_sha256=post.digest(out),prefix_unchanged=True)
    validate_carbon(folder,start,end)
    return mapping,checks


def validate_carbon(folder,start,end):
    doc=next(Path(folder).glob('*DOC_source_lambda10.h5'))
    cn=next(Path(folder).glob('*CNbc_conc_lambda10.h5'))
    with h5py.File(doc) as h:
        for i in range(start,end):
            total=h[post.DOC_KEY][str(i)][:]
            reconstructed=sum(h[f"DOC production {s} [mol m^-3 s^-1]"][str(i)][:]*c for s,c in zip(post.SPECIES,post.CARBON))
            post.require(np.isfinite(total).all() and (total>=0).all(),"Invalid DOC forcing")
            post.require(np.allclose(total,reconstructed,rtol=1e-10,atol=1e-25),"Source carbon mismatch")
    with h5py.File(cn) as h:
        total=h[post.CN_KEY][:]
        reconstructed=sum(h[f"{s} mol water basis [molS molH^-1]"][:]*c for s,c in zip(post.SPECIES,post.CARBON))
        post.require(np.allclose(total,reconstructed,rtol=1e-10,atol=1e-25),"Boundary carbon mismatch")


def generate_artificial_cases(base,config,scenario,mesh,forcing,burn,patterns,output):
    cases={};severity={"A0":"unburned/no-low","A1":"low","A2":"moderate","A3":"high"}
    for case,pattern in patterns.items():
        print("Generating",case,flush=True)
        folder=f"caselambda-run2-artificial-{case}.{scenario}"
        target,report=post.generate_case(base,config,scenario,severity[case],mesh,forcing,burn,case_name=folder)
        mapping,checks=write_case_forcing(target,config,forcing,pattern)
        execution=target/config["case"]["site_name"]
        for item in report["xml"]:
            root=ET.parse(item["output"]).getroot()
            for node in root.iter("Parameter"):
                value=node.get("value","")
                if node.get("name")=="file" and value.endswith(".h5"):
                    original=str((execution/value).resolve())
                    if original in mapping:node.set("value",os.path.relpath(mapping[original],execution))
            # Diff final XML against parent: keep the existing intended-change list,
            # plus ONLY substitutions to our isolated forcing files.
            before=post.xml_values(ET.parse(item["parent"]).getroot());after=post.xml_values(root)
            # Region names such as Shrub/Scrub contain '/', so report paths
            # cannot be reconstructed into XML-name tuples by splitting.
            allowed={change["path"] for change in item["changes"]}
            changes=[]
            for path in sorted(before.keys()|after.keys()):
                if before.get(path)==after.get(path):continue
                new=after.get(path)
                file_change=(new is not None and new.get("name")=="file" and
                             str((execution/new.get("value","")).resolve()) in mapping.values())
                post.require("/".join(path) in allowed or file_change,"Unexpected artificial XML edit: "+"/".join(path))
                changes.append(dict(path="/".join(path),before=before.get(path),after=new))
            ET.indent(root,space="  ");ET.ElementTree(root).write(item["output"],encoding="UTF-8",xml_declaration=False)
            item["changes"]=changes;item["output_sha256"]=post.digest(item["output"])
            validate_xml(root,execution,forcing["end_day"])
        report.update(case_id=case,baseline=f"observed full {artificial_baseline_year(config)} reference cycle; may include actual fire",
                      forcing_files=[mapping.get(str(Path(p).resolve()),p) for p in forcing["forcing_files"]],
                      seasonal_monthly_multipliers=pattern,forcing_copies=checks,recovery_applied=False,
                      analysis_report=str(Path(output).resolve()),runtime_ready=False)
        save_json(target/"postfire_configuration_report.json",report)
        cases[case]=str(target)
    save_json(Path(output)/"generated_cases.json",cases)
    return cases


def validate_xml(root,execution,end):
    for section in root.iter("ParameterList"):
        params={p.get("name"):p.get("value") for p in section if p.tag=="Parameter"}
        filename=params.get("file","")
        if filename.endswith(".h5"):
            with h5py.File((execution/filename).resolve()) as h:
                for key in ["x header","y header","time header","value header","row header","column header",
                            "variable name","variable name 1","variable name 2"]:
                    if key in params:post.require(params[key] in h,"Missing artificial forcing header")
                if params.get("function type")=="bilinear and time":
                    shape=(len(h[params["row header"]]),len(h[params["column header"]]))
                    post.require(h[params["value header"]]["0"].shape==shape,"Artificial spatial dimensions mismatch")
        elif filename.endswith(".exo"):
            post.require((execution/filename).is_file(),"Missing copied mesh")
    post.require(float(post.child(root,"cycle driver","end time").get("value"))==end,"Wrong end time")


def plot_templates(config,report,patterns,output):
    import matplotlib.pyplot as plt
    year,ids=template_indices(config)
    _,dates,_=canonical_dates(config)
    lai=next(p for p in report["forcing_files"] if "MODIS_LAI" in p)
    doc=next(p for p in report["forcing_files"] if p.endswith("DOC_source.h5"))
    with h5py.File(lai) as h:
        curves={v:h[f"NLCD {v} LAI [-]"][:] for v in VEGETATION}
    with h5py.File(doc) as h:
        source={i:float(h[post.DOC_KEY][str(i)][:].mean()) for i in set(year)|set(ids)}
    fig,axes=plt.subplots(3,2,figsize=(14,10))
    for row,(variable,values) in enumerate([*curves.items(),("DOC",source)]):
        original=np.array([values[i] for i in year]);repeated=np.array([values[i] for i in ids])
        baseline_year=artificial_baseline_year(config)
        axes[row,0].plot(noleap_dates(f"{baseline_year}-01-01",f"{baseline_year}-12-31"),original)
        axes[row,0].axvline(pd.Timestamp(first_postfire_year(config)[0]),color="red",linestyle="--")
        axes[row,0].set_title(variable+f": observed {baseline_year} template")
        for case,pattern in patterns.items():axes[row,1].plot(dates,repeated*annual_multiplier(pattern[variable],dates),label=case)
        axes[row,1].set_title(variable+": repeated artificial forcing");axes[row,1].legend()
        for ax in axes[row]:ax.grid(alpha=.2);ax.set_ylabel("molC m$^{-3}$ s$^{-1}$" if variable=="DOC" else "LAI")
    fig.tight_layout();fig.savefig(Path(output)/"cyclic_forcing_review.png",dpi=160);plt.show()
