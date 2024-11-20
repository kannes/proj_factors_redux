# Projection Factors Redux
A QGIS plugin to calculate various cartographic projection properties.

"Redux" of https://plugins.qgis.org/plugins/ProjFactors-gh-pages/

Click the icon in the plugins toolbar, wait a while, inspect the resulting raster layer's bands.

## Examples
### Areal Scale in EPSG:3857 (WGS 84 / Pseudo-Mercator)
![3857 areal scale](https://github.com/user-attachments/assets/57a1b919-d764-4432-9280-214d0ffaa1d6)

### Angular distortion over Europe in EPSG:3035 (ETRS89-extended / LAEA Europe)
![3035](https://github.com/user-attachments/assets/d656448c-9890-4aed-b771-8eb046abca36)

### Meridional Scale over Germany in EPSG:25832 (ETRS89 / UTM zone 32N)
![25832](https://github.com/user-attachments/assets/8de5e4cc-e7c2-4f20-a31f-e69903bf90a5)


## Technical explanation
Basically all it does is:
- Generate a point for each canvas pixel
- Transform them to WGS84
- Calculate the project CRS' projection factors for each
- Generate a raster band per projection factor
- Build a GeoTIFF with all the raster bands
- Create a VRT to add band names (workaround for PyQGIS not allowing to set raster band names)

## Notes
This plugin has been developed off and on again over several years.
From the first steps in PyQGIS until today.
Expect some weird stuff if you look at the code.
:0)

## Using pyproj directly for 4x speed

There does not seem to be a way to find out if we could safely import pyproj (i.e. if that would load a pyproj that is
using the same proj as QGIS does. I assume that even the same version number between

- QGIS' proj: `[v for v in QgsCommandLineUtils.allVersions().split("\n") if v.startswith("PROJ version")][0][13:]` (yeah, great way to find that version, I know)
- and pyproj's proj (no idea how to determine it without importing pyproj first... Version of pyproj itself != proj ...)

would not be a safe indicator.

So, you can choose to use pyproj yourself, for a ~4x speed gain:

In your `QGIS3.ini`, set

```
[ProjectionFactorsRedux]
useProj=false
```

# Thanks to
- The [proj](https://proj.org/) and [QGIS](https://www.qgis.org/) developers for being awesome
- [Nyall Dawson](https://north-road.com/) for exposing [proj's `proj_factors`](https://proj.org/en/latest/development/reference/functions.html#c.proj_factors) in PyQGIS as [QgsProjectionFactors](https://qgis.org/pyqgis/master/core/QgsProjectionFactors.html)
- [Javier Jimenez Shaw](https://javier.jimenezshaw.com/) for great feedback and ideas
- Marcel for the initial idea