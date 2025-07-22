# Rectangle Tools for Blender
This is a repository that contains an addon for Blender to conveniently and quickly draw rectangular geometry. This allows a very fast workflow for building maps.

## Operation
You can use the rectangle drawing tool in both Object and Edit modes. Simply select a mesh object and then the rectangle tool in the tool bar. It will then highlight the edge that it will extrude a rectangle from, as well as the first edge point of the new rectangle.

By default the tool will grid snap with a precision of `0.1`. You can change this precision in the tool options in the upper left corner of the 3D view.

To create the rectangle, simply press the left mouse button down, and drag out the desired size of the rectangle. It will always be aligned with the edge it is being extruded from. Once you're happy with the size, release the left mouse button and the rectangle will be extruded. To cancel the rectangle creation, you can right click.

You will also notice that you can also begin rectangles outside of the selected edge. This lets you create bigger rectangles adjacent to smaller ones. However, you can also create such rectangles by dragging out the first edgepoint and holding down `Ctrl`. This will switch the tool into a midpoint extrusion mode instead, moving both sides of the new rectangle out as you drag.

Finally, if you simply click your mouse without dragging, it will extrude the entire edge that is currently highlighted out to the current mouse position.

After any kind of extrusion is completed, the newly created edge is automatically selected for you. That lets you adjust it using the standard blender shortcuts like `r` to rotate, `s` to scale, and `g` to move.

## Installation
You can [download the latest release](https://github.com/Shirakumo/blender-rectangle-tools/releases/latest/) of our plugin directly here from GitHub. The zip file can be imported into Blender just like any other addon.

Activating the `Rectangle Tools` addon should give you a new tool in object and edit modes.
