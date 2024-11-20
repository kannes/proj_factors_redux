import logging

from typing import List, Union

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QProgressBar

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsPoint,
    QgsPointXY,
    QgsProcessingParameterRasterDestination,
    QgsProjectionFactors,
    QgsRasterBlock,
    QgsRasterFileWriter,
    QgsRectangle,
    QgsSettings,
)
from qgis.utils import iface

from proj_factors_redux.qgis_plugin_tools.tools.resources import plugin_name

from proj_factors_redux.misc import create_points, pack_values, transform_points

USE_PYPROJ = QgsSettings().value(f"/{plugin_name().replace(' ', '')}/useProj") == "true"

if USE_PYPROJ:
    import pyproj  # will crash if linked version mismatches system version https://github.com/qgis/QGIS/issues/37289


LOGGER = logging.getLogger(plugin_name())


# descriptions via https://qgis.org/pyqgis/master/core/QgsProjectionFactors.html
PROJECTION_FACTORS_QGIS = {
    "angularDistortion": "Angular Distortion",
    "arealScale": "Areal Scale",
    "dxDlam": "Partial derivative ∂x/∂λ",
    "dxDphi": "Partial derivative ∂x/∂ϕ",
    "dyDlam": "Partial derivative ∂y/∂λ",
    "dyDphi": "Partial derivative ∂y/∂ϕ",
    "meridianConvergence": "Meridian Convergence (aka Grid Declination) (in degrees)",
    "meridianParallelAngle": "Meridian Parallel Angle (in degrees)",
    "meridionalScale": "Meridional Scale",
    "parallelScale": "Parallel Scale",
    "tissotSemimajor": "Maximum scale factor (Tissot Semimajor)",
    "tissotSemiminor": "Minimum scale factor (Tissot Semiminor)",
}

# https://pyproj4.github.io/pyproj/stable/api/proj.html#pyproj.proj.Factors
# descriptions via https://qgis.org/pyqgis/master/core/QgsProjectionFactors.html
PROJECTION_FACTORS_PYPROJ = {
    "angular_distortion": "Angular Distortion",
    "areal_scale": "Areal Scale",
    "dx_dlam": "Partial derivative ∂x/∂λ",
    "dx_dphi": "Partial derivative ∂x/∂ϕ",
    "dy_dlam": "Partial derivative ∂y/∂λ",
    "dy_dphi": "Partial derivative ∂y/∂ϕ",
    "meridian_convergence": "Meridian Convergence (aka Grid Declination) (in degrees)",
    "meridian_parallel_angle": "Meridian Parallel Angle (in degrees)",
    "meridional_scale": "Meridional Scale",
    "parallel_scale": "Parallel Scale",
    "tissot_semimajor": "Maximum scale factor (Tissot Semimajor)",
    "tissot_semiminor": "Minimum scale factor (Tissot Semiminor)",
}


class GeographicCrsError(Exception):
    pass


def gather_factors(
    points: List[Union[QgsPointXY, None]],
    crs: QgsCoordinateReferenceSystem,
) -> List[Union[QgsProjectionFactors, None]]:
    """Returns the projection factors for all the points.

    The points must all be in WGS84 for proj.

    If factors could not be calculated, the list will contain a None in its place.
    """
    LOGGER.info("Calculating projection factors...")
    # coordinates must be lng/x and lat/y in wgs84

    # this is the slowest part, so it gets its own progress bar
    # via https://docs.qgis.org/testing/en/docs/pyqgis_developer_cookbook/communicating.html#showing-progress
    progress_message_bar = iface.messageBar().createMessage("Calculating projection factors...")
    progress = QProgressBar(parent=iface.mainWindow())
    progress.setMaximum(len(points))
    progress.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    progress_message_bar.layout().addWidget(progress)
    iface.messageBar().pushWidget(progress_message_bar, Qgis.Info)
    QgsApplication.processEvents()  # yolo to get the message bar to display less ugly ;D

    factors = []
    for i, pointxy in enumerate(points):
        if i % int(len(points) / 1000) == 0:  # update progress bar reasonably often
            progress.setValue(i + 1)

        # we set None if we could not transform a canvas pixel to a coordinate, e.g. OOB
        if pointxy is not None:
            x = pointxy.x()
            y = pointxy.y()
            if -90 < y < 90 and -180 < x < 180:
                point = QgsPoint(x, y)
                # TODO is this flipped sometimes?
                # proj -V wants long lat! see correct E/N values for "echo "10 53.5" | proj -V EPSG:25832"
                # so i assume this should take long lat too, so we use (x, y)

                these_factors = crs.factors(point)
                if not these_factors.isValid():
                    # happens e.g. at ~500000, 0 in EPSG:5972
                    these_factors = None
            else:
                # point is outside geographic bounds
                these_factors = None
        else:
            # list did not contain a point but None because coordinates could not be transformed in an earlier step
            these_factors = None

        factors.append(these_factors)

    iface.messageBar().clearWidgets()
    iface.messageBar().pushMessage("Done", "Factors calculated!", level=Qgis.Info)

    if None in factors:
        invalid_factors_count = factors.count(None)
        LOGGER.critical(
            f"There issues were calculating the factors for {invalid_factors_count}/{len(factors)} points..."
        )

    LOGGER.info("Calculating projection factors... Done!")
    return factors


def extract_factor(projection_factors: List[Union[QgsProjectionFactors, None]], factor: str) -> list[float]:
    """Extract the values for one specified factor from a list of QgsProjectionFactors objects.

    If the passed list contains None entries, a NaN float value will be used.
    """
    # gather the values for the factor the user selected, this is one value per "pixel"
    LOGGER.info(f"Extracting factor {factor!r} from calculated factors...")
    values = []
    use_proj = QgsSettings().value(f"/{plugin_name().replace(' ', '')}/useProj") == "true"
    for single_projection_factors in projection_factors:
        # check if factor values could not be calculated at this point, e.g. outside of bounds of EPSG:3035
        if single_projection_factors is None:
            value = float("nan")
        else:
            if use_proj:
                value = getattr(single_projection_factors, factor)  # e.g. single_projection_factors.dxDlam()
            else:
                value = getattr(single_projection_factors, factor)()  # e.g. single_projection_factors.dxDlam()
        values.append(value)
    LOGGER.info(f"Extracting factor {factor!r} from calculated factors... Done!")
    return values


def create_factors_tif(extent: QgsRectangle, crs: QgsCoordinateReferenceSystem, pixel_size: int):
    if crs.authid() == "EPSG:4326":
        raise GeographicCrsError("EPSG:4326 is not a projected CRS")

    LOGGER.info(f"{extent=}, {crs=}, {pixel_size=}".replace("<", "|"))

    points, cols, rows = create_points(extent, pixel_size)

    # proj's get_factors needs geographic coordinates
    gcs_crs = QgsCoordinateReferenceSystem.fromEpsgId(4326)  # assuming that 4326 is the right CRS to use for GCS...
    if crs != gcs_crs:
        points_gcs = transform_points(points, crs, gcs_crs)
    else:
        points_gcs = points

    # calculate the projection factors for all the coordinates
    if USE_PYPROJ:
        factors = gather_factors_pyproj(points_gcs, crs)  # each a list with one entry per point, PFs or None
    else:
        factors = gather_factors(points_gcs, crs)  # each a list with one entry per point, PFs or None

    raster_destination = QgsProcessingParameterRasterDestination(
        name=f"Projection Factors {crs.authid()}".replace(":", "_")
    )
    raster_file_path = raster_destination.generateTemporaryDestination()

    write_factors_to_tif(raster_file_path, factors, extent, crs, rows=rows, cols=cols)
    return raster_file_path


def write_factors_to_tif(
    raster_file_path: str,
    factors: List[Union[QgsProjectionFactors, None]],
    extent: QgsRectangle,
    crs: QgsCoordinateReferenceSystem,
    cols: int,
    rows: int,
) -> None:
    LOGGER.info(f"Writing data to raster {raster_file_path!r}...")
    # based on https://github.com/qgis/QGIS/blob/62463690/src/analysis/processing/qgsalgorithmconstantraster.cpp#L95

    # QGIS source has a warning about potentially "output cellsize being calculated too small" but does not say why
    # this might happen... I only observed the tiniest mismatches between the original extent and a recalculated one
    # so ... ain't going to bother. If *you* know why we should recalculate the extent, please raise an issue :)

    if USE_PYPROJ:
        projection_factors = PROJECTION_FACTORS_PYPROJ
    else:
        projection_factors = PROJECTION_FACTORS_QGIS

    writer = QgsRasterFileWriter(raster_file_path)
    writer.setOutputProviderKey("gdal")
    writer.setCreateOptions(["COMPRESS=ZSTD", "ZSTD_LEVEL=9", "TILED=YES", "PREDICTOR=3"])
    writer.setOutputFormat(QgsRasterFileWriter.driverForExtension("tif"))

    provider = writer.createMultiBandRaster(
        Qgis.DataType.Float64, cols, rows, extent, crs, nBands=len(projection_factors)
    )

    for band_index, (factor, factor_text) in enumerate(projection_factors.items(), start=1):
        LOGGER.info(f"Collecting data for {band_index}: {factor_text}...")
        block = QgsRasterBlock(Qgis.DataType.Float64, cols, rows)
        values = extract_factor(factors, factor)
        data = pack_values(values)

        assert block.width() * block.height() == len(
            values
        ), f"Raster doesn't match values: {block.width()}x{block.height()} vs. {len(values)}"

        LOGGER.info(f"Collecting data for {band_index}: {factor_text}... Done!")

        LOGGER.info(f"Writing data to raster band {band_index}...")
        block.setData(data)
        provider.writeBlock(block, band=band_index)
        provider.setNoDataValue(band_index, float("nan"))
        # TODO ~band.SetDescription(factor_text)  # seems not possible via the QGIS API, currently using a VRT instead..
        LOGGER.info(f"Writing data to raster band {band_index}... Done!")

    LOGGER.info(f"Writing data to raster {raster_file_path!r}... Done!")


def create_vrt_for_factors_tif(tif_path: str) -> str:
    """Creates a VRT with hardcoded band names for the TIF file."""
    # stupid, temporary hack to get band names...
    # https://gis.stackexchange.com/questions/483223/assigning-a-band-name-when-using-qgsrasterfilewriter-qgsrasterdataprovider
    LOGGER.info(f"Creating VRT for {tif_path!r} so that we can have band names...")

    import processing
    import xml.etree.ElementTree as ET

    if USE_PYPROJ:
        projection_factors = PROJECTION_FACTORS_PYPROJ
    else:
        projection_factors = PROJECTION_FACTORS_QGIS

    vrt = processing.run("gdal:buildvirtualraster", {"INPUT": [tif_path], "OUTPUT": f"{tif_path}.vrt"})["OUTPUT"]

    # via https://gis.stackexchange.com/questions/428677/how-do-you-label-bands-in-a-gdal-vrt-so-that-their-label-is-recognised-in-qgis
    tree = ET.parse(vrt)
    root = tree.getroot()
    for factor_name, band in zip(projection_factors.values(), root.iter("VRTRasterBand")):
        description = ET.SubElement(band, "Description")
        description.text = factor_name
    tree.write(vrt)  # Update the file on disk

    LOGGER.info(f"Creating VRT for {tif_path!r} so that we can have band names... Done!")
    return vrt


def gather_factors_pyproj(
    points,
    crs,
) -> List[Union[pyproj.proj.Factors, None]]:
    """Using pyproj directly to avoid QGIS' repeated creation and use of a transformation. ~4 times faster.

    Thanks to @jjimenezshaw for the suggestion!

    points must have geographic coordinates.
    """
    LOGGER.info("Calculating projection factors pyproj edition...")
    # coordinates must be lng/x and lat/y in wgs84

    # this is the slowest part, so it gets its own progress bar
    # via https://docs.qgis.org/testing/en/docs/pyqgis_developer_cookbook/communicating.html#showing-progress
    progress_message_bar = iface.messageBar().createMessage("Calculating projection factors pyproj edition...")
    progress = QProgressBar(parent=iface.mainWindow())
    progress.setMaximum(len(points))
    progress.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    progress_message_bar.layout().addWidget(progress)
    iface.messageBar().pushWidget(progress_message_bar, Qgis.Info)
    QgsApplication.processEvents()  # yolo to get the message bar to display less ugly ;D

    p = pyproj.Proj(crs.authid())

    factors = []
    for i, point in enumerate(points):
        if i % int(len(points) / 1000) == 0:  # update progress bar reasonably often
            progress.setValue(i + 1)

        if point is not None:
            these_factors = p.get_factors(point.x(), point.y())
        else:
            these_factors = None
        factors.append(these_factors)

    iface.messageBar().clearWidgets()
    iface.messageBar().pushMessage("Done", "Factors calculated!", level=Qgis.Info)

    if None in factors:
        invalid_factors_count = factors.count(None)
        LOGGER.critical(
            f"There issues were calculating the factors for {invalid_factors_count}/{len(factors)} points..."
        )

    LOGGER.info("Calculating projection factors... Done!")
    return factors
