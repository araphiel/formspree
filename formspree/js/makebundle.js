/** @format */
var browserify = require('browserify')
var b = browserify()
b.add('@colevscode/react-table')
b.bundle().pipe(process.stdout)
