# Projection Factors Redux
A QGIS plugin to calculate various cartographic projection properties.

"Redux" of https://plugins.qgis.org/plugins/ProjFactors-gh-pages/

Click the icon in the plugins toolbar, wait a while, inspect the resulting raster layer's bands.

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