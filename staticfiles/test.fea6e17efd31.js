    // Initially disable submit button
    document.getElementById('submitImage').disabled = true;
    // Initially disable edit button
    document.getElementById('editImage').disabled = true;

    // initialization
    testingCaseIni() // added

    // Canvas Global Settings
    var canvas1  = new fabric.Canvas('c1');

    //window.addEventListener('load', resizeCanvas);
    //window.addEventListener('resize', resizeCanvas);

    canvas1.backgroundColor = 'grey';
    fabric.Object.prototype.transparentCorners = false;
    fabric.Object.prototype.centeredScaling = true;
    fabric.Object.prototype.centeredRotation = true;
    canvas1.preserveObjectStacking = true;

    canvas1.on({
        'object:moving': updateControls,
        'object:scaling': updateControls,
        'object:resizing': updateControls,
        'object:rotating': updateControls,
    })

    // window event listener
    window.addEventListener('load', resizeCanvas);
    window.addEventListener('resize', resizeCanvas);
    document.getElementById("top-control").oninput = function() {
        if (canvas1.getObjects().length == 1) {
            var obj = canvas1.item(0)
            obj.set("top",parseInt(this.value, 10)).setCoords()
            canvas1.requestRenderAll()
        }   
    }
    document.getElementById("left-control").oninput = function() {
        if (canvas1.getObjects().length == 1) {
            var obj = canvas1.item(0)
            obj.set("left",parseInt(this.value, 10)).setCoords()
            canvas1.requestRenderAll()
        }   
    }
    document.getElementById("opacity-control").oninput = function() {
        if (canvas1.getObjects().length == 1) {
            var obj = canvas1.item(0)
            obj.set("opacity",this.value).setCoords()
            canvas1.requestRenderAll()
        }   
    }
    document.getElementById("angle-control").oninput = function() {
        if (canvas1.getObjects().length == 1) {
            var obj = canvas1.item(0)
            obj.set("angle",parseInt(this.value, 10)).setCoords()
            canvas1.requestRenderAll()
        }   
    }
    document.getElementById("scale-control").oninput = function() {
        if (canvas1.getObjects().length == 1) {
            var obj = canvas1.item(0)
            obj.scale(this.value).setCoords()
            canvas1.requestRenderAll()
        }   
    }
    document.getElementById("cornerColor").oninput = function() {
        if (canvas1.getObjects().length == 1) {
            var obj = canvas1.item(0)
            obj["cornerColor"]=this.value
            canvas1.requestRenderAll()
        }   
    }
    document.getElementById("strokecolor").oninput = function() {
        if (canvas1.getObjects().length == 1) {
            var obj = canvas1.item(0)
            obj["stroke"]=this.value
            canvas1.requestRenderAll()
        }   
    }


    // Resize the canvas1 when the document is loaded and when the window is resized.
    function resizeCanvas() {
        const container = document.getElementById('canvas1Container');

        var newWidth = container.clientWidth;

        canvas1.setWidth(newWidth);
        canvas1.setHeight(newWidth);
        canvas1.renderAll();
    }

    canvas1.renderAll();
    
    // Zoom in/out function
    canvas1.on('mouse:wheel', function(opt) {
        var delta = opt.e.deltaY;
        var zoom = canvas1.getZoom();
        zoom *= 0.999 ** delta;
        if (zoom > 20) zoom = 20;
        if (zoom < 0.01) zoom = 0.01;
        //canvas1.zoomToPoint({ x: opt.e.offsetX, y: opt.e.offsetY }, zoom);
        canvas1.zoomToPoint(new fabric.Point(canvas1.width / 2, canvas1.height / 2), zoom);
        opt.e.preventDefault();
        opt.e.stopPropagation();
    });

    function addBKGtoCanvas() {        
        // Set the MRI image as the background of the canvas1
        var mri_path = document.getElementById('imagePlaceholder1').src;
        fabric.Image.fromURL(mri_path, function(img) {
            // Set the image as the background
            canvas1.setBackgroundImage(img, canvas1.renderAll.bind(canvas1), {
                scaleX: canvas1.width / img.width,
                scaleY: canvas1.height / img.height
            });
        });
        canvas1.renderAll();
        extractMasks();
    }

    // Mask information
    var structureColors = {
        IVD: 'rgba(64, 64, 64, 0.5)', // Note: Alpha is out of 255 here
        PE: 'rgba(128, 128, 128, 0.5)',
        TS: 'rgba(192, 192, 192, 0.5)',
        AAP: 'rgba(255, 255, 255, 0.5)'
    };
    
    // event listener to track the change of the mask
    document.addEventListener("DOMContentLoaded", function() {
        var maskSelection = document.getElementById('maskSelection');

        maskSelection.addEventListener('change', function() {
            var maskID = this.value;

            if (maskID != "") {
                removeAllMask();      // This will not remove background image
            }
            var type = maskID.slice(0,-1)
            //var numID = +maskID.substring(maskID.length-1)

            var masks = usersDB[curUserID].images[curImageID][type]
            
            for (item in masks) {
                if (masks[item].id == maskID) {
                    var mask = masks[item]
                    break
                }
            }

            if (!mask) {
                console.log("Mask not found!")
                return
            }

            loadControls(mask)
            plotOnePolygon(mask)
        });
    });

    /**
     * Polygon functions
     */    
    // Polt all masks on canvas1
    function plotAllMasks() {

        removeAllMask()
        var imgObj = usersDB[curUserID].images[curImageID];
        mask_list = [];

        ["IVD","PE","TS","AAP"].forEach((item) => {
            
            for (let index in imgObj[item]) {
                var mask = imgObj[item][index]
                var points = mask.points
                mask_list.push(mask.id)

                var polygon = new fabric.Polygon(points, {    
                    stroke: mask.stroke,
                    strokeWidth: 1,
                    //fill: structureColors[cls],
                    top:mask.top,
                    left:mask.left,
                    angle:mask.angle,
                    objectCaching: false,
                    transparentCorners: false,
                    cornerColor: mask.cornerColor,
                    opacity:mask.opacity,
                });
                polygon.scale(mask.Scale);
                canvas1.add(polygon);
            }
        })
        canvas1.renderAll();
    }

    // polt one mask on canvas1
    function plotOnePolygon(mask) {
        var polygon = new fabric.Polygon(mask.points, {    
            stroke:mask.stroke,
            strokeWidth: 1,
            top:mask.top,
            left:mask.left,
            angle:mask.angle,
            objectCaching: false,
            cornerColor:mask.cornerColor,
            opacity:mask.opacity,
        });
        polygon.scale(mask.Scale);
        canvas1.add(polygon);
        canvas1.renderAll();
    }

    // where do we use this function
    function polygonPositionHandler(dim, finalMatrix, fabricObject) {
        var x = (fabricObject.points[this.pointIndex].x - fabricObject.pathOffset.x),
            y = (fabricObject.points[this.pointIndex].y - fabricObject.pathOffset.y);
        return fabric.util.transformPoint(
            { x: x, y: y },
            fabric.util.multiplyTransformMatrices(
                fabricObject.canvas1.viewportTransform,
                fabricObject.calcTransformMatrix()
            )
        );
    }

    function getObjectSizeWithStroke(object) {
        var stroke = new fabric.Point(
            object.strokeUniform ? 1 / object.scaleX : 1,
            object.strokeUniform ? 1 / object.scaleY : 1
        ).multiply(object.strokeWidth);
        return new fabric.Point(object.width + stroke.x, object.height + stroke.y);
    }

    // where do we use this function
    function actionHandler(eventData, transform, x, y) {
        var polygon = transform.target,
            currentControl = polygon.controls[polygon.__corner],
            mouseLocalPosition = polygon.toLocalPoint(new fabric.Point(x, y), 'center', 'center'),
            polygonBaseSize = getObjectSizeWithStroke(polygon),
            size = polygon._getTransformedDimensions(0, 0),
            finalPointPosition = {
                x: mouseLocalPosition.x * polygonBaseSize.x / size.x + polygon.pathOffset.x,
                y: mouseLocalPosition.y * polygonBaseSize.y / size.y + polygon.pathOffset.y
            };
        polygon.points[currentControl.pointIndex] = finalPointPosition;
        return true;
    }
    
    // define a function that can keep the polygon in the same position when we change its
    // width/height/top/left.
    function anchorWrapper(anchorIndex, fn) {
        return function(eventData, transform, x, y) {
            var fabricObject = transform.target,
                absolutePoint = fabric.util.transformPoint({
                    x: (fabricObject.points[anchorIndex].x - fabricObject.pathOffset.x),
                    y: (fabricObject.points[anchorIndex].y - fabricObject.pathOffset.y)
                }, 
                fabricObject.calcTransformMatrix()),
                actionPerformed = fn(eventData, transform, x, y),
                newDim = fabricObject._setPositionDimensions({}),
                polygonBaseSize = getObjectSizeWithStroke(fabricObject),
                newX = (fabricObject.points[anchorIndex].x - fabricObject.pathOffset.x) / polygonBaseSize.x,
                newY = (fabricObject.points[anchorIndex].y - fabricObject.pathOffset.y) / polygonBaseSize.y;
            fabricObject.setPositionByOrigin(absolutePoint, newX + 0.5, newY + 0.5);
            return actionPerformed;
        }
    }

    // allow edit the each pt in a polygon
    function Edit() {
        canvas1.forEachObject(function (obj) {
            if (obj.type === 'polygon') { // Check if it's a polygon
                obj.edit = !obj.edit; // Toggle edit mode
                if (obj.edit) {
                    var lastControl = obj.points.length - 1;
                    obj.cornerStyle = 'circle';
                    obj.cornerColor = '#0000ff';
                    obj.controls = obj.points.reduce(function (acc, point, index) {
                        acc['p' + index] = new fabric.Control({
                            positionHandler: polygonPositionHandler,
                            actionHandler: anchorWrapper(index > 0 ? index - 1 : lastControl, actionHandler),
                            actionName: 'modifyPolygon',
                            pointIndex: index
                        });
                        return acc;
                    }, {});
                } else {
                    obj.cornerColor = '#0000ff';
                    obj.cornerStyle = 'rect';
                    obj.controls = fabric.Object.prototype.controls;
                }
                obj.hasBorders = !obj.edit;
            }
        });
        canvas1.requestRenderAll();
    }

    //remove all masks on the canvas1
    function removeAllMask() {
        canvas1.remove(...canvas1.getObjects())
    }                    

    // reset mask
    function resetMask() {
        removeAllMask()
        var maskID = document.getElementById('maskSelection').value;
        var type = maskID.slice(0,-1)
        var masks = usersDB[curUserID].images[curImageID][type]
        for (item in masks) {
            if (masks[item].id == maskID) {
                var mask = masks[item]
                break
            }
        }

        loadControls(mask)
        plotOnePolygon(mask)
    }

    // save mask parameters
    function saveMask() {

        var maskID = document.getElementById('maskSelection').value;
        var type = maskID.slice(0,-1)
        var masks = usersDB[curUserID].images[curImageID][type]
        for (item in masks) {
            if (masks[item].id == maskID) {
                var mask = masks[item]
                break
            }
        }

        mask.top = parseInt(document.getElementById("top-control").value,10)
        mask.left = parseInt(document.getElementById("left-control").value,10) 
        mask.opacity = parseFloat(document.getElementById("opacity-control").value)
        mask.angle = parseInt(document.getElementById("angle-control").value,10) 
        mask.Scale = parseFloat(document.getElementById("scale-control").value)
        mask.stroke = document.getElementById("strokecolor").value
        mask.cornerColor = document.getElementById("cornerColor").value

    }

    // function to brutal delete the active obj on canvas1
    function delMask() {
        var obj = canvas1.getActiveObject();
        var result = alert("It will be removed and can't be undo")
        canvas1.remove(obj)
    }

    // use to load the parameters when the mask is first created
    function loadControls(mask) {
        document.getElementById("top-control").value = mask.top;
        document.getElementById("left-control").value = mask.left;
        document.getElementById("opacity-control").value = mask.opacity;
        document.getElementById("angle-control").value = mask.angle;
        document.getElementById("scale-control").value = mask.Scale;
        document.getElementById("cornerColor").value = mask.cornerColor;
        document.getElementById("strokecolor").value = mask.stroke;
        //document.getElementById("scaleY-control").value = mask.ScaleY;        
    }

    // function to dynamic track the object manipulation
    function updateControls() {
        var canvas1Obj = canvas1.getActiveObject()
        if (canvas1Obj) {
            document.getElementById("top-control").value = canvas1Obj.top;
            document.getElementById("left-control").value = canvas1Obj.left;
            document.getElementById("opacity-control").value = canvas1Obj.opacity;
            document.getElementById("angle-control").value = canvas1Obj.angle;
            document.getElementById("scale-control").value = canvas1Obj.scaleX;
            //document.getElementById("scaleY-control").value = mask.ScaleY;
            document.getElementById("cornerColor").value = canvas1Obj.cornerColor;
            document.getElementById("strokecolor").value = canvas1Obj.stroke; 
        }               
    }
