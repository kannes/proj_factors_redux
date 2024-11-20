# fmt: off
from qgis.core import QgsApplication
QgsApplication.setPrefixPath("/usr/bin/qgis", True)
qgs = QgsApplication([], False)
qgs.initQgis()

import unittest

import numpy

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsPointXY,
    QgsRectangle,
)

from proj_factors_redux.misc import create_points, transform_points

EXTENT = QgsRectangle(-1.5, -2.5, 2.5, 0.5)  # 4 wide, 3 high. xMin=-1.5, yMin=-2.5, xMax=2.5, yMax=1.5
CELLSIZE = 1  # cellsize 1 -> stepping through extent is on full values: -1, 0 etc.
CRS_WGS84 = QgsCoordinateReferenceSystem.fromEpsgId(4326)
CRS_UTM32N = QgsCoordinateReferenceSystem.fromEpsgId(25832)
CELL_COORDINATES = [
    (-1,  0),
    ( 0,  0),
    ( 1,  0),
    ( 2,  0),
    (-1, -1),
    ( 0, -1),
    ( 1, -1),
    ( 2, -1),
    (-1, -2),
    ( 0, -2),
    ( 1, -2),
    ( 2, -2),
]
CELL_POINTXYS = [QgsPointXY(x, y) for x, y in CELL_COORDINATES]
CELL_POINTXYS_UTM32N = transform_points(CELL_POINTXYS, CRS_WGS84, CRS_UTM32N)


class TestAxisOrderings(unittest.TestCase):
    def shortDescription(self):
        return None

    def test_test_extent_is_4x3(self):
        """Just a simple test to check if my assumptions about the test case data is correct."""
        self.assertEqual(EXTENT.width(), 4)
        self.assertEqual(EXTENT.height(), 3)

    # Adding "Point (53.550556 9.993333)" with QuickWKT while EPSG:4326 is active creates a point at the horn of Africa
    # so we *should* use the coordinates in x/y order even with EPSG:4326.

    def test_x_is_first_y_is_second_in_25832(self):
        """
        In UTM32N I am sure that I fully understand how x and y work.
        Let's see if I understand QGIS' handling of WGS84 (=axis inverted) too...
        """
        # via Wikipedia
        hamburg_wgs84 = [9.993333, 53.550556]  # first is left/right is x, second is up/down is y
        pointxy_hamburg_wgs84 = QgsPointXY(*hamburg_wgs84)
        hamburg_utm32n = [565811, 5933977]  # first is left/right is x, second is up/down is y
        pointxy_hamburg_utm32n = QgsPointXY(*hamburg_utm32n)

        # we transform the UTM32 coordinates to WGS84
        pointxy_hamburg_wgs84_from_utm32 = transform_points([pointxy_hamburg_utm32n], CRS_UTM32N, CRS_WGS84)[0]

        self.assertAlmostEqual(pointxy_hamburg_wgs84_from_utm32.x(), pointxy_hamburg_wgs84.x(), places=5)
        self.assertAlmostEqual(pointxy_hamburg_wgs84_from_utm32.y(), pointxy_hamburg_wgs84.y(), places=5)
        # yes they are almost equal if we compare like that

        # so yeah, we can treat those coordinates simply as x/y and ignore the "flipped" aspect of the system?

    def test_cells_in_extent_wgs84(self):
        # yes, even if QGIS says that this CRS is axisInverted, the coordinate values of the points are still going
        # x left to right (west to east) and y bottom to top (south to north)
        # TODO is this really really true?! see test above :) remove this line once tested
        points, _, _ = create_points(EXTENT, CELLSIZE)
        calculated_cell_coordinates = [(p.x(), p.y()) for p in points]
        self.assertListEqual(calculated_cell_coordinates, CELL_COORDINATES)

    def test_cells_in_extent_utm32n(self):
        points, _, _ = create_points(EXTENT, CELLSIZE)
        calculated_cell_coordinates = [(p.x(), p.y()) for p in points]
        self.assertListEqual(calculated_cell_coordinates, CELL_COORDINATES)

    def test_rows_cols_wgs84(self):
        _, cols, rows = create_points(EXTENT, CELLSIZE)
        self.assertEqual((cols, rows), (4, 3))

    def test_rows_cols_utm32n(self):
        _, cols, rows = create_points(EXTENT, CELLSIZE)
        self.assertEqual((cols, rows), (4, 3))

    def test_transform_points_utm32n_projV(self):
        """
        echo "-1  0" | proj -d 6 -V EPSG:25832 | grep Easting
        echo " 0  0" | proj -d 6 -V EPSG:25832 | grep Easting
        echo " 1  0" | proj -d 6 -V EPSG:25832 | grep Easting
        echo " 2  0" | proj -d 6 -V EPSG:25832 | grep Easting
        echo "-1 -1" | proj -d 6 -V EPSG:25832 | grep Easting
        echo " 0 -1" | proj -d 6 -V EPSG:25832 | grep Easting
        echo " 1 -1" | proj -d 6 -V EPSG:25832 | grep Easting
        echo " 2 -1" | proj -d 6 -V EPSG:25832 | grep Easting
        echo "-1 -2" | proj -d 6 -V EPSG:25832 | grep Easting
        echo " 0 -2" | proj -d 6 -V EPSG:25832 | grep Easting
        echo " 1 -2" | proj -d 6 -V EPSG:25832 | grep Easting
        echo " 2 -2" | proj -d 6 -V EPSG:25832 | grep Easting
        """
        eastings_via_projV = [
            -618481.324164,
            -505646.899516,
            -393126.130087,
            -280882.939159,
            -618308.573583,
            -505492.189389,
            -392989.214538,
            -280763.601974,
            -617790.381311,
            -505028.110536,
            -392578.512129,
            -280405.627933,
        ]
        eastings_via_qgis = [p.x() for p in CELL_POINTXYS_UTM32N]
        numpy.testing.assert_array_almost_equal(eastings_via_projV, eastings_via_qgis)

        northings_via_projV = [
            0.000000,
            0.000000,
            0.000000,
            0.000000,
            -112246.669259,
            -111917.105602,
            -111623.606587,
            -111365.707338,
            -224491.884086,
            -223833.173533,
            -223246.543556,
            -222731.066061,
        ]
        northings_via_qgis = [p.y() for p in CELL_POINTXYS_UTM32N]
        numpy.testing.assert_array_almost_equal(northings_via_projV, northings_via_qgis)

    def test_factors_utm32n(self):
        #factors_via_qgis
        pass


if __name__ == '__main__':
    unittest.main()

    # Finally, exitQgis() is called to remove the
    # provider and layer registries from memory
    qgs.exitQgis()
