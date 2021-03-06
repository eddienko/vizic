require('es6-promise').polyfill();
var version = require('./package.json').version;

var leaflet_marker_selector = /leaflet\/images\/marker-.*\.png/;
var leaflet_layer_icon = /leaflet\/images\/layers.*\.png/;
var fullscreen_icon = /leaflet-fullscreen\/dist\/fullscreen.*\.png/;
var path = require('path');

var loaders = [
    { test: /\.json$/, loader: 'json-loader' },
    { test: /\.css$/, loader: 'style-loader!css-loader' },

    // Generic file loader, Should be used for anything but leaflet's
    // marker-icon.png, marker-icon-2x.png or marker-shadow.png
    { test: /\.(jpg|png|gif|svg)$/, loader: 'file', exclude: [leaflet_marker_selector,fullscreen_icon]},

    // Files marker-icon.png, marker-icon-2x.png or marker-shadow.png
    // should be copied over to the bundle without being changed.
    //
    // The way it is loaded in leafletjs is:
    //
    // var path = L.Icon.Default.imagePath;
    //
    //  if (!path) {
    //      throw new Error('Couldn\'t autodetect
    //      L.Icon.Default.imagePath, set it manually.');
    //  }
    //
    //  return path + '/marker-' + name + '.png';
    //
    { test: leaflet_marker_selector, loader: 'file?name=[name].[ext]' },
    { test: leaflet_layer_icon, loader: 'file?name=[name].[ext]' },
    { test: fullscreen_icon, loader: 'file?name=[name].[ext]' },
];

module.exports = [
    {// Notebook extension
        entry: './src/extension.js',
        output: {
            filename: 'extension.js',
            path: '../vizic/static',
            libraryTarget: 'amd'
        }
    },
    {// vizic bundle for the notebook
        entry: './src/index.js',
        output: {
            filename: 'index.js',
            path: '../vizic/static',
            libraryTarget: 'amd'
        },
        devtool: 'source-map',
        module: {
            loaders: loaders
        },
        resolve:{
            root: [
                path.resolve("./node_modules"),
                path.resolve("./src")
            ]
        },
        externals: ['jupyter-js-widgets']
    },
    // {// embeddable jupyter-leaflet bundle
    //     entry: './src/embed.js',
    //     output: {
    //         filename: 'index.js',
    //         path: './dist/',
    //         libraryTarget: 'amd',
    //         publicPath: 'https://unpkg.com/jupyter-leaflet@' + version + '/dist/'
    //     },
    //     devtool: 'source-map',
    //     module: {
    //         loaders: loaders
    //     },
    //     resolve:{
    //         root: [
    //             path.resolve("./node_modules"),
    //             path.resolve("./src")
    //         ]
    //     },
    //     externals: ['jupyter-js-widgets']
    // }
];
