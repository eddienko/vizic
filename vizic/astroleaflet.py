from __future__ import print_function
from traitlets import *
from ipywidgets import *
from .leaflet import Map, RasterLayer, Layer
import pymongo as pmg
import pandas as pd
import numpy as np
import uuid
import json
import requests
from notebook.utils import url_path_join
from .utils import cut_tree, get_mst, get_m_index, get_vert_bbox
from .connection import Collection


class AstroMap(Map):
    """The map class, in charge of the overall operations.

    AstroMap extends the ``Map`` class from ``ipyleaflet`` with added rich
    features to display and interact with visualized astronomical catalogs and
    custom overlays.

    Note:
        Class attribute ``center`` is always in the form of ``[lat, lng]``.

    Keyword Args:
        zoom(int): Initial zoom for the map. Defaults to 1.
        max_zoom(int): Allowd maximum zoom level for the map. Defaults to 12.
        position_control(bool): Whether to show projected mouse position
            on the left bottom corner of the map window. Defaults to True.
        fullscreen_control(bool): Whether to allow full screen mode. Defaults
            to True.
    """

    @default('layout')
    def _default_layout(self):
        return Layout(height='512px', width='512px')
    inertia = Bool(False).tag(sync=True, o=True)
    scroll_wheel_zoom = Bool(True).tag(sync=True, o=True)
    wheel_debounce_time = Int(60).tag(sync=True, o=True)
    wheel_px_per_zoom_level = Int(60).tag(sync=True, o=True)
    zoom = Int(1).tag(sync=True, o=True)
    max_zoom = Int(12).tag(sync=True, o=True)
    position_control = Bool(True).tag(sync=True, o=True)
    fullscreen_control = Bool(True).tag(sync=True, o=True)
    fade_animation = Bool(True).tag(sync=True, o=True)
    _des_crs = List(help='Coordinate system specification').tag(sync=True)
    pan_loc = List(help='Target coordinate for panning').tag(sync=True)
    selection = Bool(False, help='Lasso-like selection status(on/off)').tag(sync=True)
    s_bounds = List(help='LatLngBounds for selection tool').tag(sync=True)
    # pan_ready = Bool(False).tag(sync=True)

    def __init__(self, **kwargs):
        """
        Args:
            **kwargs: Optional arguments for map settings.
        """
        super(AstroMap, self).__init__(**kwargs)
        if self.default_tiles is not None:
            self.default_tiles._map = self
            self._des_crs = self.default_tiles._des_crs
            self.max_zoom = self.default_tiles.max_zoom
            if self.center == [0.0, 0.0]:
                self.center = self.default_tiles.center
            self.default_tiles.visible = True

    def add_layer(self, layer):
        """Add layer to map.

        Args:
            layer: layer object to be added to the map.
        """
        if layer.model_id in self.layer_ids:
            raise LayerException('layer already on map: %r' % layer)
        layer._map = self
        if isinstance(layer, GridLayer):
            self._des_crs = layer._des_crs
            self.max_zoom = layer.max_zoom
            self.center = layer.center
        self.layers = tuple([l for l in self.layers] + [layer])
        layer.visible = True

    def remove_layer(self, layer):
        """Remove layer from map.

        Args:
            layer: layer object to be removed from the map.
        """
        if layer.model_id not in self.layer_ids:
            raise LayerException('layer not on map: %r' % layer)
        # if isinstance(layer, GridLayer):
        #     self._des_crs = [0, 0, 1, 1]
        self.layers = tuple([l for l in self.layers if l.model_id != layer.model_id])
        layer.visible = False

    def clear_layers(self):
        """Remove all existing layers from map."""
        self.layers = ()

    def center_map(self):
        """Reset the zoom and location of the map."""
        center = []
        try:
            center.append(self._des_crs[0]+128*self._des_crs[2])
            center.append(self._des_crs[1]-128*self._des_crs[3])
            self.fly_to(center, 1)
        except:
            print('No base tiles added!')

    def fly_to(self, lnglat, zoom):
        """Set view of the map to a specified zoom and location.

        Args:
            lnglat: A list containing the RA and DEC for target locations.
            zoom: An integer representing the target zoom level.

        """
        latlng = [lnglat[1],lnglat[0]]
        latlng.append(zoom)
        self.pan_loc = latlng
        self.pan_loc = []


class GridLayer(RasterLayer):
    """Base tilelayer class for hosting visualized catalogs.

    Keyword Args:
        df: A pandas dataframe where the data to be visualized is stored.
        min_zoom(int): Minimum zoom level for the tileLayer. Defaults to 0.
        max_zoom(int): Maximum zoom level for the tileLayer. Defaults to 8.
        collection(str): The name for the MongoDB documents collection
            that stores pre-ingested data.
        color(str): Preset color for visualized objects. Defaults to red.
        df_rad(int): The raidus of the circles representing objects in the
            catalog when size information is provided. Defaults to 2.
        scale_r(float): A float number indicating the scaling ratio for
            visualized objects. Defaults to 1.0.

    """
    _view_name = Unicode('LeafletGridLayerView').tag(sync=True)
    _model_name = Unicode('LeafletGridLayerModel').tag(sync=True)

    bottom = Bool(False).tag(sync=True)
    _des_crs = List().tag(Sync=True)
    df = Instance(pd.DataFrame, allow_none=True)
    min_zoom = Int(0).tag(sync=True, o=True)
    max_zoom = Int(8).tag(sync=True, o=True)
    # tile_size = Int(256).tag(sync=True, o=True)
    detect_retina = Bool(False).tag(sync=True, o=True)
    collection = Unicode().tag(sync=True, o=True)
    x_range = Float(1.0).tag(sync=True, o=True)
    y_range = Float(1.0).tag(sync=True, o=True)
    color = Unicode('red').tag(sync=True, o=True)
    # color object by property value
    custom_c = Bool(False).tag(sync=True)
    c_min_max = List().tag(sync=True)
    c_field = Unicode().tag(sync=True)
    c_map = Int(1).tag(sync=True)
    radius = Bool(False).tag(sync=True, o=True)
    point = Bool(False).tag(sync=True, o=True)
    df_rad = Int(2).tag(sync=True, o=True)
    scale_r = Float(1.0).tag(sync=True, o=True)
    c_lock = Bool(False, help='Lock on objects coloring method.').tag(sync=True)

    # color by catalogs
    c_by_c = Bool(False, help='Color the map by different catalogs').tag(sync=True, o=True)
    # filter by property range
    filter_obj = Bool(False, help="Fileter object by property value range").tag(sync=True)
    filter_property = Unicode(help="The proerty field used to sort objects").tag(sync=True)
    filter_range = List().tag(sync=True)
    center = List().tag(sync=True)
    obj_catalog = Instance(pd.Series, allow_none=True)
    __minMax = {}
    _popup_callbacks = Instance(CallbackDispatcher, ())

    @observe('c_by_c')
    def _update_cat_color(self, change):
        if change['new'] is True:
            self.custom_c = False
            self.c_lock = True
        else:
            self.c_lock = False

    @observe('custom_c')
    def _update_color_src(self, change):
        if change['new'] is True:
            self.c_min_max = []
            self.c_by_c = False
            self.c_lock = True
        else:
            self.c_min_max = []
            self.c_lock = False

    @validate('c_field')
    def _valid_field(self, proposal):
        if self.custom_c is False and not proposal['value'] == '':
            raise TraitError('Activate color by properties before ' +
                             'assigning a field to use')
        return proposal['value']

    @observe('c_field')
    def _update_c_min_max(self, change):
        if self.custom_c is True and self.c_field in self.get_fields():
            self.c_min_max = self.__minMax[change['new']]
        elif self.custom_c is False and change['new'] == '':
            pass
        else:
            raise Exception('Color Field ({}) not valid!'.format(self.c_field))
            self.c_field = change['old']

    @observe('filter_obj')
    def _update_filter(self, change):
        if change['new'] is True and self.filter_property in self.get_fields():
            self.filter_range = self.__minMax[self.filter_property]
        elif change['new'] is False:
            self.filter_range = []
            # self.filter_property = ''

    @observe('filter_property')
    def _update_property(self, change):
        if self.filter_obj is True and self.filter_property in self.get_fields():
            self.filter_range = self.__minMax[change['new']]
        elif self.filter_property not in self.get_fields():
            self.filter_property = ''

    def __init__(self, connection, coll_name=None, map_dict=None, **kwargs):
        """
        Args:
            connection: A wrapper for MongoDB connections.
            coll_name(str): The collection name for a new catalog to be ingested
                into the database. Default is None.
            **kwargs: Arbitrary keyword arguments.
        """
        super(GridLayer, self).__init__(**kwargs)
        try:
            self.db = connection.db
        except:
            raise Exception('Mongodb connection error! Check connection object!')

        if map_dict is not None:
            for k in map_dict.keys():
                self.df[k] = self.df[map_dict[k]]

        self.connection = connection
        self._server_url = connection._url
        self._checkInput(coll_name, map_dict)
        self.push_data(self._server_url)
        self._popup_callbacks.register_callback(self._query_obj, remove=False)
        self.on_msg(self._handle_leaflet_event)

        print('Mongodb collection name is {}'.format(self.collection))

    def _checkInput(self, coll_name, map_dict):
        """Check data source.

        If a string specifying the collection name for stored catalog is given
        in the instructor, the catalog metadata will be retrived from the
        database and assigned to the GridLayer object. If a pandas dataframe
        containing the catalog is provided in the instructor, the catalog will
        be formated and ingested into the database using provided ``coll_name``
        or a randomly generated string by ``uuid``.

        Args:
            coll_name: MongoDB collection name for the new catalog.
            map_dict(dict): Dataframe columns mapping dictionary.
        """

        coll = Collection()
        exist_colls = self.db.collection_names()

        if not self.collection == '':
            if self.collection not in exist_colls:
                raise Exception('Provided collection does not exist!')
            coll = self.connection.read_meta(self.collection)
        elif self.df is not None:
            clms = [x.upper() for x in list(self.df.columns)]

            if not set(['RA', 'DEC']).issubset(set(clms)):
                raise Exception("RA, DEC is required for visualization!")
            if not set(['A_IMAGE', 'B_IMAGE', 'THETA_IMAGE']).issubset(set(clms)):
                print('No shape information provided')
                if 'RADIUS' in clms:
                    print('Will use radius for filtering!')
                    coll.radius = True
                else:
                    print('Object as point, slow performance!')
                    coll.point = True

            if coll_name is not None and coll_name in exist_colls:
                raise Exception('Collectoin name already exists, try to use a different name or use existing collection.')
            df_r, coll._des_crs = self.connection._data_prep(self.df, coll)
            coll.x_range = coll._des_crs[2]*256
            coll.y_range = coll._des_crs[3]*256

            # drop created mapped columns before ingecting data
            if map_dict is not None:
                col_keys = [x.upper() for x in map_dict.keys()
                            if x.upper() not in ['RA', 'DEC']]
                df_r.drop(col_keys,axis=1, inplace=True)
                for k in col_keys:
                    coll._minMax.pop(k, None)

            # check if name given, if not using uuid
            if coll_name is not None:
                coll.name = coll_name
            else:
                coll_id = str(uuid.uuid4())
                coll.name = coll_id

            self.connection._insert_data(df_r, coll)
        else:
            raise Exception('Need to provide a collection name or a pandas dataframe!')

        # now assign collection object values to GridLayer
        self._des_crs = coll._des_crs
        self.x_range = coll.x_range
        self.y_range = coll.y_range
        self.point = coll.point
        self.radius = coll.radius
        self.__minMax = coll._minMax
        self.cat_ct = coll.cat_ct
        self.collection = coll.name

        # The center is required, don't remove
        self.center = [self._des_crs[1]-self.y_range/2, self._des_crs[0]+self.x_range/2]

    def push_data(self, url):
        """Update server extension with newly displayed catalog.

        Send basic information of this tileLayer using Rest API to the server
        for directing data request from the front-end.

        Args:
            url(str): The Jupyter server address.
        """

        mRange = (self.x_range + self.y_range)/2
        body = {
            'collection': self.collection,
            'mrange': mRange,
            'maxzoom': self.max_zoom
        }
        push_url = url_path_join(url, '/rangeinfo/')
        req = requests.post(push_url, data=body)

    def update_meta(self):
        """Update meta information after new data added."""

        coll = self.connection.read_meta(self.collection)
        self._des_crs = coll._des_crs
        self.x_range = coll.x_range
        self.y_range = coll.y_range
        self.__minMax = coll._minMax
        self.cat_ct = coll.cat_ct
        # update info at Jupyter server
        self.push_data(self._server_url)
        # update the AstroMap meta
        self._map.center = self.center = [self._des_crs[1]-self.y_range/2, self._des_crs[0]+self.x_range/2]
        self._map._des_crs = self._des_crs

    def _handle_leaflet_event(self, _, content, buffers):
        """Handle leaflet events trigged."""
        if content.get('event', '') == 'popup: click':
            self._popup_callbacks(**content)

    def _query_obj(self, **kwargs):
        """Query database for clicked object."""
        body = {'coll': self.collection,'RA': kwargs['RA'], 'DEC': kwargs['DEC']}
        popup_url = url_path_join(self._server_url, '/objectPop/')
        result = requests.get(popup_url, data=body)
        pop_dict = json.loads(result.text[1:-1])
        self.obj_catalog = pd.Series(pop_dict)

    def get_fields(self):
        """Return float properties in the catalog."""
        return self.__minMax.keys()

    def get_min_max(self, field):
        """Return the min/max value in specified catalog property.

        Args:
            field: The name of the specified property.

        Raises:
            Exception: If the provided property is not a float property or such
                a property doesn't exist in the catalog.
        """
        field = field.upper()
        if field in list(self.get_fields()):
            return self.__minMax[field]
        else:
            raise Exception('Error: {} not in database!'.format(field))

    def _query_selection(self):
        """Query selected objects.

        Query the databaes for enclosed objects by the selection bound at the
        frond-end. The query result is parsed into a pandas dataframe and
        assigned to ``select_data`` attribute.
        """
        selection_url = url_path_join(self._server_url, '/selection/')
        if self._map.s_bounds != []:
            bounds = self._map.s_bounds
            body = {
                'coll': self.collection,
                'swlng': bounds[0],
                'swlat': bounds[2],
                'nelng': bounds[1],
                'nelat': bounds[3],
            }
            res = requests.get(selection_url, data=body)
            selection_dict = json.loads(res.text)
            self.select_data = pd.DataFrame(selection_dict)
        else:
            print('bounds for selection is empty')


class VoronoiLayer(Layer):
    """Voronoi Diagram Layer.

    Using the catalog data displayed by the GridLayer to compute and display
    Voronoi Diagram.

    Keyword Args:
        color(str): Color for the overlayed diagram. Defaults to #88b21c.
        svg_zoom(int): Initial zoom for projecting the Voronoi diagram onto the
            screen. The higher the zoom the better the resolution and accuracy.
            Defaults to 5.

    """
    _view_name = Unicode('LeafletVoronoiLayerView').tag(sync=True)
    _model_name = Unicode('LeafletVoronoiLayerModel').tag(sync=True)
    voronoi_url = Unicode().tag(sync=True)
    visible = Bool(False).tag(sync=True)
    color = Unicode('#88b21c', help='Color of the links').tag(sync=True, o=True)
    svg_zoom = Int(5, help='initial zoom for projection').tag(sync=True, o=True)

    def __init__(self, gridLayer, **kwargs):
        """
        Args:
            gridLayer: A gridLayer instance.
            **kwargs: Arbitrary keyword arguments.

        Raises:
            Exception: If the gridLayer object doesn't have a connected
                database.
        """
        super(VoronoiLayer, self).__init__(**kwargs)
        try:
            self.db = gridLayer.db
        except:
            raise Exception('Mongodb connection error! Check connection object!')
        self._server_url = gridLayer._server_url
        self.voronoi_url = url_path_join(self._server_url, '/voronoi/{}.json'.format(gridLayer.collection))


class DelaunayLayer(Layer):
    """Delaunay Triangulation Layer.

    Using the catalog data displayed by the GridLayer to compute and
    display Delaunay Triangulation.

    Keyword Args:
        color(str): Color for the overlayed Triangulation. Defaults to blue.
        svg_zoom(int): Initial zoom for projecting the Delaunay triangulation
        onto the screen. The higher the zoom the better the resolution
        and accuracy. Defaults to 5.
    """
    _view_name = Unicode('LeafletDelaunayLayerView').tag(sync=True)
    _model_name = Unicode('LeafletDelaunayLayerModel').tag(sync=True)
    delaunay_url = Unicode().tag(sync=True)
    visible = Bool(False).tag(sync=True)
    color = Unicode('blue').tag(sync=True, o=True)
    svg_zoom = Int(5).tag(sync=True, o=True)

    def __init__(self, gridLayer, **kwargs):
        """
        Args:
            gridLayer: A gridLayer instance.
            **kwargs: Arbitrary keyword arguments.

        Raises:
            Exception: If the gridLayer object doesn't have a
                connected database.
        """
        super(DelaunayLayer, self).__init__(**kwargs)
        try:
            self.db = gridLayer.db
        except:
            raise Exception('Mongodb connection error! Check connection object!')
        self._server_url = gridLayer._server_url
        self.delaunay_url = url_path_join(self._server_url, '/voronoi/{}.json'.format(gridLayer.collection))


class HealpixLayer(Layer):
    """Healpix grid Layer.

    Using the catalog data displayed by a given tileLayer to compute
    and display Healpix pixelization grid.

    Keyword Args:
        color(str): Color for the overlayed Healpix grid. Defaults to white.
        svg_zoom(int): Initial zoom for projecting Healpix grid onto the screen.
            The higher the zoom the better the resolution and accuracy.
            Defaults to 5.
        nside(int) : Healpix resolution given by nside parameters for the
        input pixel, dafaults to 1024. It must be a power of 2, less than 2**30.
        nest(bool): Pixelization schema, True: Nested Schema, False: Ring
            Schema. Defaults to True.
    """
    _view_name = Unicode('LeafletHealpixLayerView').tag(sync=True)
    _model_name = Unicode('LeafletHealpixLayerModel').tag(sync=True)
    _healpix_url = Unicode().tag(sync=True)
    visible = Bool(False).tag(sync=True)
    color = Unicode('white').tag(sync=True, o=True)
    svg_zoom = Int(5).tag(sync=True, o=True)
    nside = Int(1024)
    nest = Bool(True)

    def __init__(self, gridLayer, **kwargs):
        """
        Args:
            gridLayer: A gridLayer instance.
            **kwargs: Arbitrary keyword arguments.

        Raises:
            Exception: If the gridLayer object doesn't have a
                connected database.
        """
        super(HealpixLayer, self).__init__(**kwargs)
        # Check for parameters regarding Healpix, i.e, nside and nest
        if 'nside' in kwargs:
            self.nside = int(kwargs["nside"])
        if 'nest' in kwargs:
            self.nest = bool(kwargs["nest"])
        # '_id' field for this particular healpix grid data in Mongodb
        document_id = gridLayer.collection+'_'+str(self.nside)+'_'+str(self.nest)
        try:
            self.db = gridLayer.db
        except:
            raise Exception('Mongodb connection error! Check connection object!')
        # print(self.collection)
        if self.db['healpix'].find({'_id':document_id}).count() < 1:
            self.inject_data(gridLayer, document_id)

        self._server_url = gridLayer._server_url
        self._healpix_url = url_path_join(self._server_url, '/healpix/{}.json'.format(document_id))

    def inject_data(self, gridLayer, document_id):
        """Import computed Healpix grid into the database"""
        # [xmin, xmax, ymin, ymax]
        self.bbox = [gridLayer._des_crs[0],gridLayer._des_crs[1]-gridLayer.y_range, gridLayer._des_crs[0]+gridLayer.x_range, gridLayer._des_crs[1]]
        all_v = get_vert_bbox(self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3], self.nside, self.nest)
        polys = [{'ra':x[0].tolist(), 'dec': x[1].tolist()} for x in all_v]
        # inject data into mongodb
        self.db['healpix'].insert_one({'_id':document_id, 'data':polys})


class CirclesOverLay(Layer):
    """Circles overlay class.

    Overlay a group of circles using data provided in a pandas dataframe or a
    document ID for stored data in the database.

    Keyword Args:
        color(str): Color for the overlayed circles. Defaults to purple.
        svg_zoom(int): Initial zoom for projecting circles onto the screen.
            The higher the zoom the better the resolution and accuracy.
            Defaults to 5.
        df: A pandas dataframe containing the positions for the circles to be
        drawn. Raidus for these circles could also be specified here.
        raidus(int): The raidus of the circles drawn measured in pixels.
            Defaults to 50 pixels.
        cols: A list indicating the position columns name. Defauts to
            [``RA``, ``DEC``]. A third entry can be provided to indicate the
            radius column.
    """
    _view_name = Unicode('LeafletCirclesLayerView').tag(sync=True)
    _model_name = Unicode('LeafletCirclesLayerModel').tag(sync=True)
    circles_url = Unicode().tag(sync=True)
    visible = Bool(False).tag(sync=True)
    color = Unicode('purple').tag(sync=True, o=True)
    svg_zoom = Int(5).tag(sync=True, o=True)
    df = Instance(pd.DataFrame, allow_none=True)
    radius = Int(50).tag(sync=True, o=True)
    cols = List(['RA', 'DEC'])

    def __init__(self, gridLayer, name, **kwargs):
        """
        Args:
            gridLayer: A gridLayer instance.
            name: The document ID for data stored in the database or a new
                user-defined ID for new data.
            **kwargs: Arbitrary keyword arguments.

        """
        super(CirclesOverLay, self).__init__(**kwargs)
        try:
            self.db = gridLayer.db
        except:
            raise Exception('Mongodb connection error! Check connection object!')
        self.document_id = name

        if self.db['circles'].find({'_id':name}).count() < 1:
            if self.df is None:
                raise Exception('Given overlay data id does not exist, a dataframe is required.')
            self.inject_data(name)

        self._server_url = gridLayer._server_url
        self.circles_url = url_path_join(self._server_url, '/circles/{}.json'.format(name))

    def inject_data(self, document_id):
        """Import data to the database"""
        dff = self.df.copy()
        dff.columns = [x.upper() for x in dff.columns]
        cols = [x.upper() for x in self.cols]
        data = dff[cols].to_dict(orient='records')

        coll = self.db['circles']
        coll.insert_one({'_id':document_id, 'data':data})


class MstLayer(Layer):
    """Minimum spanning tree (MST) overlay class.

    Layer class for MST computed using the catalog visualized by the base
    tileLayer with added features to cut the tree by maximum edge length
    and minimum branch size (the number edges in a branch).

    Keyword Args:
        color(str): Color for the overlayed MST. Defaults to ``#0459e2``.
        svg_zoom(int): Initial zoom for projecting MST onto the screen.
            The higher the zoom the better the resolution and accuracy.
            Defaults to 5.
    """
    _view_name = Unicode('LeafletMstLayerView').tag(sync=True)
    _model_name = Unicode('LeafletMstLayerModel').tag(sync=True)
    mst_url = Unicode().tag(sync=True)
    # cut_tree = Bool(False).tag(sync=True)
    max_len = Float(0.0).tag(sync=True)
    visible = Bool(False).tag(sync=True)
    color = Unicode('#0459e2').tag(sync=True, o=True)
    svg_zoom = Int(5).tag(sync=True, o=True)
    line_idx = List().tag(sync=True)
    _cut_count = Int(0).tag(sync=True)

    def __init__(self, gridLayer, neighbors=15, **kwargs):
        """
        Note:
            To speed the calculation, Vizic retains the index of non-zero
            element in the MST sparse matrix.

        Args:
            gridLayer: A gridLayer instance.
            neighbors: Vizic uses ``kneighbors_graph`` from sklearn to compute
                spanning trees for each set of points. The higher the number
                of neighbors used, the higher the precision.
            **kwargs: Arbitrary keyword arguments.

        Raises:
            Exception: If the gridLayer object doesn't have a connected
                database.
        """
        super(MstLayer, self).__init__(**kwargs)
        try:
            self.db = gridLayer.db
        except:
            raise Exception('Mongodb connection error! Check connection object!')
        self.document_id = gridLayer.collection

        if self.db['mst'].find({'_id':self.document_id}).count() < 1:
            self.inject_data(neighbors)
        else:
            self.get_index()

        self._server_url = gridLayer._server_url
        self.mst_url = url_path_join(self._server_url, '/mst/{}.json'.format(self.document_id))

    def inject_data(self, neighbors):
        """Calculate and import MST data into the database."""
        coll = self.db[self.document_id]
        cur_ls = list(coll.find({'_id':{'$ne':'meta'}},{'_id':0,'RA':1,'DEC':1}))
        df_pos = pd.DataFrame(cur_ls)
        m, index = get_mst(df_pos, neighbors)
        self.index = index
        mst_lines = m.to_dict(orient='records')
        self.db['mst'].insert_one({'_id':self.document_id, 'tree':mst_lines})

    def get_index(self):
        """Retrive the index of the saved MST matrix"""
        coll = self.db['mst']
        cur_ls = list(coll.find({'_id':self.document_id}))
        # lines_ls = cur_ls['tree']
        df_pos = pd.DataFrame(cur_ls[0]['tree'])
        self.index = get_m_index(df_pos)

    def cut(self, length, members):
        """Cut the MST.

        Args:
            length(float): Maximum edge length.
            members(int): The minimum number of edges in each saved branch.
        """
        self.line_idx = cut_tree(self.index, length, members)
        self.max_len = float(length)
        self._cut_count += 1

    def recover(self):
        self.max_len = 0.0

    def get_data(self):
        """Retrive the MST edges data from the database."""
        coll = self.db['mst']
        cur_ls = list(coll.find({'_id':self.document_id}))
        return cur_ls[0]['tree']
