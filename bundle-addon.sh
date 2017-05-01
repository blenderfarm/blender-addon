#!/bin/sh

# Bundles all the necessary files into a single `.zip` that Blender understands.

if [[ $# -eq 0 ]] ; then
    echo 'expected single argument pointing at `core` git directory'
    echo 'usage: ' $0 ' <core-git-directory>'
    echo '  where <core-git-directory> is the root directory of https://github.com/blenderfarm/core'
    exit 0
fi

rm dist -rf
mkdir dist

mkdir render_blenderfarm/
mkdir render_blenderfarm/blenderfarm/
mkdir render_blenderfarm/blenderfarm/api/

cp __init__.py render_blenderfarm/
cp $1/blenderfarm/*.py render_blenderfarm/blenderfarm/
cp $1/blenderfarm/api/*.py render_blenderfarm/blenderfarm/api/

zip render_blenderfarm.zip render_blenderfarm/ -r

rm render_blenderfarm/ -rf

mv render_blenderfarm.zip dist
