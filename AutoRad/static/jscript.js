// Global variables to store information
var curUserID;
var curImageID;
var globalMaskClassPaths = [];  // This variable is used in other places to record the image path, think about pypass this function to DB
var mask_path;
var mask_list = [];
// var query_result={}

// unknow variables, need validatation or removed.
var structureLayers = [];

// Test users DB to keep all the records and information
var usersDB = {}

/**
 * Query the SQLite3 created by django
 * @param {string} objType 
 * @param {int} objID 
 */
function queryDBInfo(objType,objID) {

    var data = JSON.stringify({'objType':objType,'objID':objID});
    var csrftoken = getCSRFToken();
    var query_result = {}
    $.ajax({
        type: 'POST',
        url: '/api/query-info/',
        data: data,
        contentType: 'application/json',
        beforeSend: function (xhr) {
            if (csrftoken) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        },
        success: function (response) {
            
            query_result = response
            console.log("Query DB Successfully!")
            console.log("==================================")
            console.log(query_result)
            console.log("==================================")
            return response
        }
    })
}

/**
 * function based on old EditMask function, the API call to obtain the masks information 
 */
function extractMasks() {

    var mri_path = document.getElementById('imagePlaceholder1').src;
    var imgID = document.getElementById('imagePlaceholder1').getAttribute('value');
    var data = JSON.stringify({'mask_url': mri_path,'imgID':imgID});
    var csrftoken = getCSRFToken();

    $.ajax({
        type: 'POST',
        url: '/api/get-control-points/',
        data: data,
        contentType: 'application/json',
        beforeSend: function (xhr) {
            if (csrftoken) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        },
        success: function (response) {
            if (response.cls_cnt != "") {
                console.log("pnts calculated successfully!")
            } else {
                console.log("pnts calculated error!")
            }
            // var contours = response.cls_cnt;
            // Object.keys(contours).forEach(function (cls){
            //     contours[cls].forEach(function (contour){
            //         var points = contour.map(function (pointWrapper){
            //             var point = pointWrapper[0];
            //             return {x: point[0], y: point[1]};
            //         });
            //         console.log(cls,": ",points)
            //     });
            // });
        }
    });
}    

/**
 * Get CSRF Token from cookies
 */
function getCSRFToken() {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
        var cookie = jQuery.trim(cookies[i]);
        if (cookie.substring(0, 'csrftoken'.length + 1) === 'csrftoken=') {
            return decodeURIComponent(cookie.substring('csrftoken'.length + 1));
        }
    }
    return null;
}

// function to control the behavior of "select all" checkbox
function selectAll() {
    var dropdown = document.getElementById("maskSelection")
    var checkAllBox = document.getElementById("selectAllChkBox")

    if (checkAllBox.checked) {
        dropdown.disabled = true
    } else {
        dropdown.disabled = false
    }
}

//function to extract the mask_list for select image
function createOptionsMask() {
    var dropdownList = document.getElementById("maskSelection")
    
    var index = dropdownList.options.length
    for (let i=index-1;i>0;i--) {
        dropdownList.remove(i)
    }

    mask_list.forEach(option => {
        var opt = document.createElement("option")
        opt.value=option
        opt.textContent=option
        dropdownList.appendChild(opt)
    })
}

// function to hide the image list card on home.html
function hideImageList() {
    var imgList = document.getElementById("imagesList")
    document.getElementById('imageManipulationCard').hidden = false
    imgList.hidden = true
}

// function to show the image list card on home.html
function showImageList() {
    var imgList = document.getElementById("imagesList")
    document.getElementById('imageManipulationCard').hidden = true
    imgList.hidden = false
}

// Function triggered when select an image under the currect user 
function loadThisImg(obj) {
    hideImageList()
    imgSrc = obj.getAttribute('src')
    imgID = obj.getAttribute('value')
    $('#imagePlaceholder1').attr('src',imgSrc)
    $('#imagePlaceholder1').attr('value',imgID)
    document.getElementById('editImage').disabled = false
    var maskSrc = imgSrc.split('.')[0] + '.jpg'
    $('#imagePlaceholder2').attr('src',maskSrc)
}

/**
 * saveImg.html
 */
// Function triggered when submit button is clicked. It will show the uploaded image and reflect the information on the page.
function addNewImage() {
    var imageInput = document.getElementById('imageUpload')
    var saveBtn = document.getElementById('saveBtn')
    if (imageInput.files && imageInput.files[0]) {
        var reader = new FileReader();
        reader.readAsDataURL(imageInput.files[0]);
        reader.onload = (function(e) {
            var image = new Image();
            image.src = e.target.result;
            image.onload = function() {
                // console.log(this.naturalHeight);
                // console.log(this.naturalWidth);
                document.getElementById("imgWidth").value = this.naturalWidth
                document.getElementById("imgHeight").value = this.naturalHeight
                $('#imageBox').attr('src', this.src);
            };
        })
        // console.log(imageInput.files[0].name)
        // console.log(imageInput.files[0].type)
        document.getElementById("imgName").value = imageInput.files[0].name
        document.getElementById("imgType").value = imageInput.files[0].type

        saveBtn.disabled = false
    } else {
        saveBtn.disabled = true
    }
}

/**
 * delImg.html
 */


//===============================
// Unused Function below
//===============================

// /**
//  * user class for DB 
//  */
// class user {

//     constructor(username,userpwd) {
        
//         this.userDict = {
//             username:username,
//             password:userpwd,
//             images:{}
//         }
//     }

//     addToUsers() {
//         this.userID = generateUUID("user")
//         console.log("New user added to database: " + this.userID)
//         usersDB[this.userID]=this.userDict
//     }

//     deleteUser() {
//         delete usersDB[this.userID]
//     }
// }

// /**
//  * class of image for autoRad. Need modify the file name in future
//  */
// class autoRadImage {

//     constructor(srcString,imgName) {
//         this.imgDict = {
//             src:srcString,
//             saveName:"unSavedImage.png",    // Purpose to save the name for human readable purpose
//             IVD:[],
//             PE:[],
//             TS:[],
//             AAP:[]
//         }
//     }

//     addToUser(userId) {
//         this.imageID = generateUUID("image")
//         console.log("New image " + `${this.imageID}` + " added to user: " + userId)
//         usersDB[userId].images[this.imageID] = this.imgDict
//     }

//     delImage(userId) {
//         delete usersDB[userId].images[this.imageID]
//     }
// }

// /**
//  * Image mask class. Need some work on initial position.
//  */
// class imgMask {

//     constructor(typeStr,idNum,ptArr) {

//         var canvasWidth = parseInt(document.getElementById("c1").style.width.slice(0,-2))
//         var scaleRatio = canvasWidth/500

//         var minLeft = canvasWidth;
//         var minTop = canvasWidth;

//         for (let pts in ptArr) {
//             if (ptArr[pts].x < minLeft) minLeft=ptArr[pts].x
//             if (ptArr[pts].y < minTop) minTop=ptArr[pts].y
//         }

//         this.maskDict = {
//             id:typeStr+idNum,
//             points:ptArr,
//             top:minTop * scaleRatio,
//             left:minLeft * scaleRatio,
//             angle:0,
//             Scale:scaleRatio,
//             opacity:0.8,
//             // cornColor:"#ff0000",        //red
//             cornerColor:"#0000ff",        //blue
//             stroke:"#ff0000"                //red
//         }
//     }

//     addToImage(userId, imageId, typeStr) {
//         console.log("A new "+typeStr+" mask is added under image: " + imageId + " under user: " + userId)
//         usersDB[userId].images[imageId][typeStr].push(this.maskDict)
//     }

//     delMask(userId, imageId, typeStr) {
//         delete usersDB[userId].images[imageId][typeStr]
//     }
// }

// /**
//  * function to generate unique ID with prefix, ID is based on prefx_date_random string
//  */
// function generateUUID(prefixString) {
//     var timeStamp = Date.now().toString(36);
//     var randomValue = Math.random().toString(36).substring(2, 15);
//     return(`${prefixString}-${timeStamp}-${randomValue}`)
// }

// /**
//  * function to initial testing userDB with testing user (one)
//  */
// function testingCaseIni() {
//     var testUser = new user("Lijia","12345678")
//     testUser.addToUsers()

//     curUserID=testUser.userID
// }

// /**
//  * [Old]function to initial images with the select image.
//  */
// function testingImgIni() {
//     var img = new autoRadImage(document.getElementById("imagePlaceholder1").src)
//     img.addToUser(curUserID)

//     curImageID = img.imageID
// }

// /**
//  * function to add masks to the image selected under logged user
//  */
// function masksToImgDB(userID, imgID, typeString, ptsArr) {

//     var imgs = usersDB[userID].images[imgID][typeString]
//     var idNum = imgs.length
//     var maskTemp = new imgMask(typeString,idNum+1, ptsArr)
//     maskTemp.addToImage(userID,imgID,typeString)
// }

// /**
//  * [Not used]function to check whether the image exists under the curUser using src.
//  * @param {*} userID 
//  * @param {*} src 
//  * @returns 
//  */
// function isImgExist(userID, src) {
//     var imgs = usersDB[userID].images
//     if (Object.keys(imgs).length != 0) {
//         for (let imgId in imgs) {
//             if (imgs[imgId].src == src) {
//                 return true
//             }
//         }
//     }
//     return false
// }

// /**
//  * function to locate or create the image based on src under current logged user 
//  * return the imageID
//  */
// function getImgID(userID, src) {

//     var imgs = usersDB[userID].images

//     if (Object.keys(imgs).length != 0) {
//         for (let imgId in imgs) {
//             // console.log(imgId)
//             if (imgs[imgId].src == src) {
//                 console.log("Image found in DB: " + imgId)
//                 return [true,imgId]
//             }
//         }
//     }    

//     var tempImg = new autoRadImage(src)
//     tempImg.addToUser(userID)
//     console.log("New image added to user: " + userID)
//     return [false, tempImg.imageID]
// }

// /**
//  * Image upload image function
//  */
// function handleImageUpload() {
//     var imageInput = document.getElementById('imageUpload');
//     var submitButton = document.getElementById('submitImage');
//     if (imageInput.files && imageInput.files[0]) {
//         // Enable the submit button
//         submitButton.disabled = false;
//         // Display the uploaded image
//         displayUploadedImage();
//     } else {
//         // Disable the submit button if no image is chosen
//         submitButton.disabled = true;
//     }
// }

// /**
//  * Display upload image function in image place holder 1. Meanwhile, some button enable/disable.
//  */
// function displayUploadedImage() {
//     var input = document.getElementById('imageUpload');
//     var editButton = document.getElementById('editImage');
//     if (input.files && input.files[0]) {
//         var reader = new FileReader();

//         reader.onload = function(e) {
//             $('#imagePlaceholder1').attr('src', e.target.result);
//         }

//         reader.readAsDataURL(input.files[0]);
//         editButton.disabled = false
//     }
//     else {
//         editButton.disabled = true
//     }
// }

// /**
//  * This function will upload the image to the model and generate the components output png files in media folder 
//  */
// function uploadImage() {
//     var formData = new FormData();
//     formData.append('image', $('#imageUpload')[0].files[0]);
//     var csrftoken = getCSRFToken();

//     $.ajax({
//         type: 'POST',
//         url: '/api/process-image/',
//         data: formData,
//         processData: false,
//         contentType: false,
//         beforeSend: function(xhr) {
//             if (csrftoken) {
//                 xhr.setRequestHeader("X-CSRFToken", csrftoken);
//             }
//         },
//         success: function(response) {
//             // Extract relevant data from the response
//             var maskUrl = response.mask_url;

//             // Second API call: view_mask
//             $.ajax({
//                 type: 'POST',
//                 url: '/api/view-mask/',
//                 data: JSON.stringify({ 'mask_url': maskUrl }),  // Pass relevant data to the second API
//                 contentType: 'application/json',
//                 beforeSend: function(xhr) {
//                     if (csrftoken) {
//                         xhr.setRequestHeader("X-CSRFToken", csrftoken);
//                     }
//                 },
//                 success: function(viewMaskResponse) {
//                     $('#imagePlaceholder2').attr('src', viewMaskResponse.mask_url)
//                     globalMaskClassPaths = viewMaskResponse.mask_class_paths;
//                     mask_path = viewMaskResponse.mask_url;
//                 },
//                 error: function(xhr, status, error) {
//                     console.error('Failed to call view_mask:', xhr.responseText, status, error);
//                 }
//             });
//         },
//         error: function() {
//             console.error('Error processing image');
//         }
//     });
// }