import logging
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from qgis.core import (
    Qgis,
    QgsProject,
    QgsRasterLayer,
)
from qgis.gui import QgsSingleBandPseudoColorRendererWidget
from qgis.utils import iface

from proj_factors_redux.qgis_plugin_tools.tools.custom_logging import setup_logger
from proj_factors_redux.qgis_plugin_tools.tools.resources import (
    plugin_name,
    resources_path,
)

from proj_factors_redux.factoring import (
    create_factors_tif,
    create_vrt_for_factors_tif,
    GeographicCrsError,
)


setup_logger(plugin_name())
LOGGER = logging.getLogger(plugin_name())
LOGGER.setLevel(logging.DEBUG)


def classFactory(iface):
    return ProjFactorsRedux(iface)


class ProjFactorsRedux:

    def __init__(self, iface):
        icon = QIcon(os.path.join(resources_path("icons", "icon.png")))
        self.action = QAction(icon, "Calculate Projection Factors for Canvas", iface.mainWindow())

    def initGui(self):
        self.action.triggered.connect(self.run)
        iface.addToolBarIcon(self.action)

    def unload(self):
        iface.removeToolBarIcon(self.action)
        del self.action

    def run(self):
        iface.messageBar().pushMessage(
            plugin_name(),
            "Calculating projection factors for canvas...",
            level=Qgis.Info,
        )

        extent = iface.mapCanvas().extent()
        crs = iface.mapCanvas().mapSettings().destinationCrs()
        pixel_size = iface.mapCanvas().getCoordinateTransform().mapUnitsPerPixel()

        if crs.authid() == "EPSG:4326":
            iface.messageBar().pushMessage(
                plugin_name(),
                f"CRS must be projected, {crs.authid()} isn't!",
                level=Qgis.Critical,
            )
            return

        raster_file_path = create_factors_tif(extent, crs, pixel_size)

        # FIXME hack because qgis cannot add band names
        # https://gis.stackexchange.com/questions/483223/assigning-a-band-name-when-using-qgsrasterfilewriter-qgsrasterdataprovider
        # this is a workaround that adds band names via vrt...
        vrt_path = create_vrt_for_factors_tif(raster_file_path)

        iface.messageBar().pushMessage(plugin_name(), f"Raster written to {raster_file_path}", level=Qgis.Success)

        # load the result as single band pseudocolor via Kalak at https://gis.stackexchange.com/a/469859/51035, thanks!
        # Name: "Projection Factors EPSG:XXXXX"
        layer_name = os.path.basename(raster_file_path)[:-4].replace("_", ":")
        layer = QgsRasterLayer(vrt_path, baseName=layer_name)
        layer.setRenderer(QgsSingleBandPseudoColorRendererWidget(layer).renderer())
        QgsProject.instance().addMapLayer(layer)
