import logging
import struct

from typing import List, Union

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCsException,
    QgsMapToPixel,
    QgsMultiPoint,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
)
from qgis.gui import QgsMapCanvas

from proj_factors_redux.qgis_plugin_tools.tools.resources import plugin_name


LOGGER = logging.getLogger(plugin_name())


def angular_brackets_to_html(string: str):
    """Replaces < and > with &lt; and &gt; to work around QGIS MessageLog's annoying HTML parsing..."""
    return string.replace("<", "&lt;").replace(">", "&gt;")


def pack_values(values: List[float], data_type: int = "d") -> bytes:
    """Packs the passed values into a bytes object.

    Args:
        values: The float values to pack
        data_type: The type to use for packing. Defaults to "d" (8 byte double / Float64)
                   Refer to https://docs.python.org/3.12/library/struct.html#format-characters
    """
    # for 1920x1080 values as doubles this is a ~200MB bytes object
    LOGGER.info(f"Packing {len(values)} values...")
    fmt = f"{len(values)}{data_type}"
    data = struct.pack(fmt, *values)
    LOGGER.info(f"Packing {len(values)} values... Done!")
    return data


def create_points(extent: QgsRectangle, step_size: int):
    """Creates points in extent with a configurable step size.

    The outermost points are placed 0.5*step_size inwards.
    """

    def frange(start, stop, step):
        # via https://stackoverflow.com/a/4189815
        # TODO use this really? move to misc? just inline this code?
        i = 0
        while start + i * step < stop:
            yield start + i * step
            i += 1

    # some iffy logic around floats and integers below :\
    points = []
    cols = round(extent.width() / step_size)
    rows = round(extent.height() / step_size)

    # from y max to y min, x min to x max = top to bottom, left to right
    for y in reversed(list(frange(extent.yMinimum() + step_size * 0.5, extent.yMaximum(), step_size))):
        for x in frange(extent.xMinimum() + step_size * 0.5, extent.xMaximum(), step_size):
            point = QgsPointXY(x, y)
            points.append(point)

    # missing one row sometimes:
    assert rows * cols == len(points), f"{rows * cols=} vs. {len(points)=}"
    # happens sometimes... TODO build test cases
    return points, cols, rows


def transform_points(
    points: list[QgsPointXY],
    source_crs: QgsCoordinateReferenceSystem,
    target_crs: QgsCoordinateReferenceSystem,
) -> List[Union[QgsPointXY, None]]:
    """Returns the points transformed to the target CRS.

    If a point could not be transformed, the list will contain a None in its place.
    """
    LOGGER.info(f"Transforming {len(points)} points to EPSG:4326...")

    coordinate_transform_to_gcs = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())

    transformed_points = []
    for point in points:
        try:
            point_gcs = coordinate_transform_to_gcs.transform(point)
        except QgsCsException:
            # will happen if no forward transform is possible
            # e.g. if out of bounds coordinates are visible in the canvas ("off world") for 25832 or robinson
            point_gcs = None
        transformed_points.append(point_gcs)

    LOGGER.info(f"Transforming {len(points)} points to EPSG:4326... Done!")
    return transformed_points


def transform_points_multipoint_THIS_TAKES_MORE_THAN_TWICE_AS_LONG(
    points: list[QgsPointXY],
    source_crs: QgsCoordinateReferenceSystem,
    target_crs: QgsCoordinateReferenceSystem,
) -> List[Union[QgsPointXY, None]]:
    # converts the points list to a single multipoint object first
    coordinate_transform_to_gcs = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    multipoint = QgsMultiPoint(points)
    multipoint.transform(coordinate_transform_to_gcs)
    transformed_points = [QgsPointXY(multipoint.pointN(n)) for n in range(multipoint.nCoordinates())]
    return transformed_points


def canvas_pixel_points(canvas: QgsMapCanvas) -> List[QgsPointXY]:
    """Returns QgsPointXYs for all pixels of a rect with a coordinate transform (e.g. the canvas...).

    Order for gdal: top left to bottom right (flip_y=True)
    Order for pyqgis: bottom left to top right (flip_y=False)
    """
    LOGGER.info("Generating points for canvas pixels...")

    coordinate_transform: QgsMapToPixel = canvas.getCoordinateTransform()
    width = coordinate_transform.mapWidth()
    height = coordinate_transform.mapHeight()
    LOGGER.info(f"{width=} x {height=} is {width*height} pixels")

    points: List[QgsPointXY] = [
        coordinate_transform.toMapCoordinates(x, y) for y in range(height) for x in range(width)
    ]
    LOGGER.info(f"Generated {len(points)=} points.")
    assert len(points) == width * height

    LOGGER.info("Generating points for canvas pixels... Done!")
    return points
