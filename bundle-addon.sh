#!/bin/sh

# Bundles all the necessary files into a single `.zip` that Blender understands.

rm dist -rf
mkdir dist

mkdir render_blenderfarm/
mkdir render_blenderfarm/blenderfarm/

cp __init__.py render_blenderfarm/
cp $1/blenderfarm/*.py render_blenderfarm/blenderfarm/

zip render_blenderfarm.zip render_blenderfarm/ -r

rm render_blenderfarm/ -rf

mv render_blenderfarm.zip dist
